/* CortexForge in-canvas behavioural task engine.
 *
 * Security notes:
 *  - All DOM insertion via textContent, never innerHTML.
 *  - No eval, no Function constructor, no third-party scripts.
 *  - Loaded after app.js; uses the same el() helper pattern.
 */
'use strict';

/* ---------------------------------------------------------------- helpers */

function el(tag, opts = {}, children = []) {
  const node = document.createElement(tag);
  if (opts.class) node.className = opts.class;
  if (opts.text !== undefined) node.textContent = String(opts.text);
  if (opts.attrs) for (const [k, v] of Object.entries(opts.attrs)) node.setAttribute(k, v);
  for (const c of children) node.appendChild(c);
  return node;
}

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function showInstructions(container, title, text, buttonText) {
  return new Promise((resolve) => {
    container.replaceChildren();
    const card = el('div', { class: 'card task-instructions-card' });
    card.appendChild(el('h2', { text: title }));
    card.appendChild(el('p', { class: 'lede', text: text }));
    const btn = el('button', { class: 'primary magic-border', text: buttonText || 'Begin' });
    card.appendChild(btn);
    container.appendChild(card);
    btn.addEventListener('click', () => { container.replaceChildren(); resolve(); });
  });
}

function clearContainer(container) {
  container.replaceChildren();
}

/* ------------------------------------------------------- TaskEngine core */

const TaskEngine = {
  _renderers: {},

  register(taskId, renderer) {
    this._renderers[taskId] = renderer;
  },

  has(taskId) {
    return taskId in this._renderers;
  },

  async run(taskId, container, config = {}) {
    const renderer = this._renderers[taskId];
    if (!renderer) throw new Error('Unknown task: ' + taskId);
    clearContainer(container);
    return await renderer(container, config);
  }
};

/* ---------------------------------------------------------------- flanker */

TaskEngine.register('flanker', async function(container, config = {}) {
  const nTrials = config.trials || 40;
  const fixationMs = 500;
  const stimulusMs = 1500;
  const itiMs = 300;

  await showInstructions(
    container,
    'Flanker Task',
    'A row of arrows will appear. Respond to the CENTER arrow as quickly as possible.\n\n' +
    'Press LEFT arrow key if the center arrow points left (←).\n' +
    'Press RIGHT arrow key if the center arrow points right (→).\n\n' +
    'You can also click the buttons below.',
    'Start'
  );

  const trials = [];
  let prevError = false;

  for (let i = 0; i < nTrials; i++) {
    const congruent = Math.random() < 0.5;
    const centerDir = Math.random() < 0.5 ? 'left' : 'right';
    const flankDir = congruent ? centerDir : (centerDir === 'left' ? 'right' : 'left');

    const arrows = [];
    for (let j = 0; j < 5; j++) {
      arrows.push(j === 2 ? centerDir : flankDir);
    }

    const trial = await runFlankerTrial(container, arrows, congruent, fixationMs, stimulusMs, itiMs);
    trial.prev_error = prevError;
    prevError = !trial.correct;
    trials.push(trial);
  }

  return trials;
});

function runFlankerTrial(container, arrows, congruent, fixationMs, stimulusMs, itiMs) {
  return new Promise((resolve) => {
    const area = el('div', { class: 'card task-stimulus-card' });
    container.appendChild(area);

    area.appendChild(el('div', {
      class: 'task-fixation',
      attrs: { 'aria-hidden': 'true' },
      text: '+'
    }));

    let responded = false;
    let stimulusStart = 0;
    let timeoutId = null;
    let keyHandler = null;

    const cleanup = () => {
      if (timeoutId) clearTimeout(timeoutId);
      if (keyHandler) document.removeEventListener('keydown', keyHandler);
      area.replaceChildren();
    };

    const respond = (dir) => {
      if (responded) return;
      responded = true;
      const rt = Math.round(performance.now() - stimulusStart);
      const correct = dir === arrows[2];
      cleanup();
      setTimeout(() => {
        resolve({ congruent, correct, rt_ms: rt, prev_error: false });
      }, itiMs);
    };

    setTimeout(() => {
      if (responded) return;
      area.replaceChildren();

      const arrowRow = el('div', { class: 'task-arrows', attrs: { role: 'group', 'aria-label': 'Arrow stimulus' } });
      arrows.forEach(dir => {
        arrowRow.appendChild(el('span', {
          class: 'task-arrow' + (dir === arrows[2] ? ' target' : ''),
          text: dir === 'left' ? '←' : '→'
        }));
      });
      area.appendChild(arrowRow);

      const btnRow = el('div', { class: 'row' });
      const leftBtn = el('button', { class: 'magic-border', text: '← Left', attrs: { 'aria-label': 'Respond left' } });
      const rightBtn = el('button', { class: 'magic-border', text: 'Right →', attrs: { 'aria-label': 'Respond right' } });
      leftBtn.addEventListener('click', () => respond('left'));
      rightBtn.addEventListener('click', () => respond('right'));
      btnRow.appendChild(leftBtn);
      btnRow.appendChild(rightBtn);
      area.appendChild(btnRow);

      stimulusStart = performance.now();

      keyHandler = (e) => {
        if (e.key === 'ArrowLeft') { e.preventDefault(); respond('left'); }
        else if (e.key === 'ArrowRight') { e.preventDefault(); respond('right'); }
      };
      document.addEventListener('keydown', keyHandler);

      timeoutId = setTimeout(() => {
        if (responded) return;
        responded = true;
        cleanup();
        setTimeout(() => {
          resolve({ congruent, correct: false, rt_ms: stimulusMs, prev_error: false });
        }, itiMs);
      }, stimulusMs);
    }, fixationMs);
  });
}

/* ------------------------------------------------- pattern_comparison */

TaskEngine.register('pattern_comparison', async function(container, config = {}) {
  const nTrials = config.trials || 90;
  const windowSec = config.window || 90;

  await showInstructions(
    container,
    'Pattern Comparison',
    'Two grids of squares will appear side by side.\n\n' +
    'Press S if the two patterns are the SAME.\n' +
    'Press D if the two patterns are DIFFERENT.\n\n' +
    'You have ' + windowSec + ' seconds to complete as many trials as you can.',
    'Start'
  );

  const trials = [];
  const startTime = performance.now();
  const windowMs = windowSec * 1000;

  for (let i = 0; i < nTrials; i++) {
    if (performance.now() - startTime >= windowMs) break;

    const isSame = Math.random() < 0.5;
    const gridA = generateGrid();
    let gridB;

    if (isSame) {
      gridB = gridA.slice();
    } else {
      gridB = gridA.slice();
      const nChanges = 1 + Math.floor(Math.random() * 3);
      const positions = shuffle([...Array(16).keys()]);
      for (let c = 0; c < nChanges; c++) {
        const pos = positions[c];
        gridB[pos] = gridB[pos] === 1 ? 0 : 1;
      }
    }

    const trial = await runPatternTrial(container, gridA, gridB, isSame);
    trials.push(trial);
  }

  return trials;
});

function generateGrid() {
  const grid = [];
  for (let i = 0; i < 16; i++) {
    grid.push(Math.random() < 0.5 ? 1 : 0);
  }
  return grid;
}

function renderGrid(container, grid, label) {
  const wrap = el('div', { class: 'task-grid-wrap' });
  wrap.appendChild(el('div', { class: 'task-grid-label', text: label }));
  const gridEl = el('div', { class: 'task-grid', attrs: { role: 'img', 'aria-label': label } });
  for (let i = 0; i < 16; i++) {
    const cell = el('div', { class: 'task-cell' + (grid[i] ? ' filled' : '') });
    gridEl.appendChild(cell);
  }
  wrap.appendChild(gridEl);
  return wrap;
}

function runPatternTrial(container, gridA, gridB, isSame) {
  return new Promise((resolve) => {
    const area = el('div', { class: 'card task-stimulus-card' });
    container.appendChild(area);

    const gridsRow = el('div', { class: 'task-grids-row' });
    gridsRow.appendChild(renderGrid(area, gridA, 'Pattern A'));
    gridsRow.appendChild(renderGrid(area, gridB, 'Pattern B'));
    area.appendChild(gridsRow);

    const btnRow = el('div', { class: 'row' });
    const sameBtn = el('button', { class: 'magic-border', text: 'S — Same', attrs: { 'aria-label': 'Patterns are the same' } });
    const diffBtn = el('button', { class: 'magic-border', text: 'D — Different', attrs: { 'aria-label': 'Patterns are different' } });
    btnRow.appendChild(sameBtn);
    btnRow.appendChild(diffBtn);
    area.appendChild(btnRow);

    let responded = false;
    const stimulusStart = performance.now();
    let keyHandler = null;

    const cleanup = () => {
      if (keyHandler) document.removeEventListener('keydown', keyHandler);
      area.replaceChildren();
    };

    const respond = (saidSame) => {
      if (responded) return;
      responded = true;
      const rt = Math.round(performance.now() - stimulusStart);
      const correct = saidSame === isSame;
      cleanup();
      resolve({ correct, rt_ms: rt });
    };

    sameBtn.addEventListener('click', () => respond(true));
    diffBtn.addEventListener('click', () => respond(false));

    keyHandler = (e) => {
      if (e.key === 's' || e.key === 'S') { e.preventDefault(); respond(true); }
      else if (e.key === 'd' || e.key === 'D') { e.preventDefault(); respond(false); }
    };
    document.addEventListener('keydown', keyHandler);
  });
}

/* ------------------------------------------------------------ ultimatum */

TaskEngine.register('ultimatum', async function(container, config = {}) {
  const nTrials = config.trials || 20;
  const half = Math.floor(nTrials / 2);

  await showInstructions(
    container,
    'Ultimatum Game',
    'You will play two roles in a resource-splitting game.\n\n' +
    'PROPOSER: You decide how to split $10 between yourself and another player.\n' +
    'RESPONDER: You decide whether to accept or reject an offer made to you.\n\n' +
    'If the responder accepts, both get the proposed split. If they reject, both get nothing.',
    'Start'
  );

  const trials = [];

  for (let i = 0; i < half; i++) {
    const trial = await runProposerTrial(container, i, half);
    trials.push(trial);
  }

  for (let i = 0; i < half; i++) {
    const trial = await runResponderTrial(container, i, half);
    trials.push(trial);
  }

  return trials;
});

function runProposerTrial(container, idx, total) {
  return new Promise((resolve) => {
    const area = el('div', { class: 'card task-stimulus-card' });
    container.appendChild(area);

    area.appendChild(el('h3', { text: 'Proposer ' + (idx + 1) + ' of ' + total }));
    area.appendChild(el('p', {
      class: 'lede',
      text: 'You have $10. Enter how much you want to keep for yourself. The other player gets the rest.'
    }));

    const slider = el('input', {
      attrs: { type: 'range', min: '0', max: '10', step: '0.5', value: '5', 'aria-label': 'Amount to keep for yourself' }
    });
    const sliderVal = el('span', { class: 'task-slider-val', text: '$5.00' });

    slider.addEventListener('input', () => {
      sliderVal.textContent = '$' + Number(slider.value).toFixed(2);
    });

    const sliderRow = el('div', { class: 'task-slider-row' });
    sliderRow.appendChild(slider);
    sliderRow.appendChild(sliderVal);
    area.appendChild(sliderRow);

    const otherVal = el('span', { class: 'task-slider-val', text: '$5.00' });
    const otherRow = el('div', { class: 'task-slider-row' });
    otherRow.appendChild(el('span', { text: 'Other player gets:' }));
    otherRow.appendChild(otherVal);
    area.appendChild(otherRow);

    slider.addEventListener('input', () => {
      otherVal.textContent = '$' + (10 - Number(slider.value)).toFixed(2);
    });

    const btn = el('button', { class: 'primary magic-border', text: 'Submit offer' });
    btn.addEventListener('click', () => {
      const offer = Number(slider.value);
      area.replaceChildren();
      resolve({ role: 'proposer', offer: offer, accepted: true });
    });
    area.appendChild(btn);
  });
}

function runResponderTrial(container, idx, total) {
  return new Promise((resolve) => {
    const area = el('div', { class: 'card task-stimulus-card' });
    container.appendChild(area);

    const offer = Math.round(Math.random() * 20) / 2;

    area.appendChild(el('h3', { text: 'Responder ' + (idx + 1) + ' of ' + total }));
    area.appendChild(el('p', {
      class: 'lede',
      text: 'The other player proposes to keep $' + offer.toFixed(2) + ' and give you $' + (10 - offer).toFixed(2) + '.'
    }));
    area.appendChild(el('p', {
      class: 'lede',
      text: 'Do you ACCEPT or REJECT this offer? If you reject, both players get nothing.'
    }));

    const btnRow = el('div', { class: 'row' });
    const acceptBtn = el('button', { class: 'primary magic-border', text: 'Accept' });
    const rejectBtn = el('button', { class: 'magic-border', text: 'Reject' });

    acceptBtn.addEventListener('click', () => {
      area.replaceChildren();
      resolve({ role: 'responder', offer: offer, accepted: true });
    });
    rejectBtn.addEventListener('click', () => {
      area.replaceChildren();
      resolve({ role: 'responder', offer: offer, accepted: false });
    });

    btnRow.appendChild(acceptBtn);
    btnRow.appendChild(rejectBtn);
    area.appendChild(btnRow);
  });
}

/* ---------------------------------------------- social_value_orientation */

const SVO_ALLOCATIONS = [
  { self: 5, other: 0 },
  { self: 5, other: 1 },
  { self: 5, other: 2 },
  { self: 5, other: 3 },
  { self: 5, other: 4 },
  { self: 5, other: 5 },
  { self: 4, other: 5 },
  { self: 3, other: 5 },
  { self: 2, other: 5 },
  { self: 1, other: 5 },
  { self: 0, other: 5 },
  { self: 4, other: 4 },
  { self: 3, other: 3 },
  { self: 2, other: 2 },
  { self: 1, other: 1 },
  { self: 0, other: 0 },
  { self: 4, other: 3 },
  { self: 3, other: 4 },
  { self: 2, other: 3 },
  { self: 3, other: 2 },
  { self: 1, other: 2 },
  { self: 2, other: 1 },
  { self: 0, other: 1 },
  { self: 1, other: 0 }
];

TaskEngine.register('social_value_orientation', async function(container, config = {}) {
  const nTrials = config.trials || 24;

  await showInstructions(
    container,
    'Social Value Orientation',
    'For each item, choose the allocation you most prefer.\n\n' +
    'Each option shows how many points you would receive and how many points another person would receive.\n' +
    'There are no right or wrong answers — choose what you genuinely prefer.',
    'Start'
  );

  const trials = [];
  const allocations = shuffle(SVO_ALLOCATIONS).slice(0, nTrials);

  for (let i = 0; i < allocations.length; i++) {
    const trial = await runSVOTrial(container, i, allocations.length, allocations[i]);
    trials.push(trial);
  }

  return trials;
});

function runSVOTrial(container, idx, total, allocation) {
  return new Promise((resolve) => {
    const area = el('div', { class: 'card task-stimulus-card' });
    container.appendChild(area);

    area.appendChild(el('h3', { text: 'Item ' + (idx + 1) + ' of ' + total }));
    area.appendChild(el('p', {
      class: 'lede',
      text: 'Choose the allocation you prefer. "You" = points for you, "Other" = points for another person.'
    }));

    const options = shuffle([
      { self: allocation.self, other: allocation.other },
      { self: allocation.other, other: allocation.self },
      { self: Math.max(0, allocation.self - 1), other: Math.min(5, allocation.other + 1) },
      { self: Math.min(5, allocation.self + 1), other: Math.max(0, allocation.other - 1) }
    ]);

    const fieldset = el('fieldset', { class: 'task-svo-options' });
    fieldset.style.border = 'none';
    fieldset.style.padding = '0';

    const legend = el('legend', { text: 'Select one:' });
    fieldset.appendChild(legend);

    options.forEach((opt, oi) => {
      const label = el('label', { class: 'task-svo-option' });
      const radio = el('input', {
        attrs: { type: 'radio', name: 'svo_' + idx, value: String(oi) }
      });
      label.appendChild(radio);
      label.appendChild(el('span', {
        text: 'You: ' + opt.self + '  |  Other: ' + opt.other
      }));
      fieldset.appendChild(label);
    });

    area.appendChild(fieldset);

    const btn = el('button', { class: 'primary magic-border', text: 'Confirm' });
    btn.disabled = true;

    fieldset.addEventListener('change', () => { btn.disabled = false; });

    btn.addEventListener('click', () => {
      const selected = fieldset.querySelector('input:checked');
      if (!selected) return;
      const opt = options[Number(selected.value)];
      area.replaceChildren();
      resolve({ self: opt.self, other: opt.other });
    });

    area.appendChild(btn);
  });
}

/* --------------------------------------------------------- false_belief */

const FALSE_BELIEF_VIGNETTES = [
  {
    story: 'Sarah puts her favourite book on the kitchen table and goes to answer the door. While she is gone, her brother Tom moves the book to the living room shelf. Sarah comes back inside. Where does Sarah think Tom will look for the book?',
    options: [
      'On the kitchen table',
      'On the living room shelf',
      'In Sarah\'s bedroom',
      'In Tom\'s backpack'
    ],
    correct: 0
  },
  {
    story: 'Maya tells her friend Alex that she has hidden a surprise gift under her bed before leaving for school. While Maya is at school, her mother finds the gift and moves it to the closet. When Maya comes home, where does she believe the gift is?',
    options: [
      'In the closet',
      'Under her bed',
      'In the kitchen',
      'At Alex\'s house'
    ],
    correct: 1
  },
  {
    story: 'David sees his teacher place a box of markers on the desk before leaving the classroom. After the teacher leaves, a student moves the box to the supply cabinet. The teacher returns. Where does the teacher think the box of markers is?',
    options: [
      'In the supply cabinet',
      'On the floor',
      'On the desk',
      'In the student\'s hand'
    ],
    correct: 2
  },
  {
    story: 'Emma hides a key in a drawer before going to the park. Her sister Lily, who was not present when Emma hid the key, comes home and moves the key to a vase on the mantel. Where does Emma think Lily believes the key is?',
    options: [
      'In the vase on the mantel',
      'In the drawer',
      'Under the doormat',
      'In Emma\'s pocket'
    ],
    correct: 1
  },
  {
    story: 'Jake puts his wallet on the nightstand before taking a shower. His roommate, who did not see Jake put the wallet there, moves it to the dresser while Jake is showering. Where does Jake think his roommate will look for the wallet?',
    options: [
      'On the dresser',
      'On the nightstand',
      'In the bathroom',
      'In Jake\'s jacket'
    ],
    correct: 1
  },
  {
    story: 'Olivia tells her colleague Mark that she left a report on the shared printer before going to a meeting. While she is in the meeting, Mark files the report in the cabinet. Where does Olivia think Mark believes the report is?',
    options: [
      'In the cabinet',
      'On the shared printer',
      'In Olivia\'s email',
      'In the recycling bin'
    ],
    correct: 1
  },
  {
    story: 'A chef places a bowl of soup on the counter and steps into the pantry. A waiter, unaware the soup is there, moves it to the stove. Where does the chef think the waiter will look for the bowl of soup?',
    options: [
      'On the stove',
      'In the pantry',
      'On the counter',
      'In the refrigerator'
    ],
    correct: 2
  },
  {
    story: 'Nina leaves her umbrella by the front door before going upstairs. Her brother, who came home after Nina left, hangs the umbrella in the closet. Where does Nina think her brother believes the umbrella is?',
    options: [
      'In the closet',
      'By the front door',
      'In the car',
      'At Nina\'s office'
    ],
    correct: 1
  }
];

TaskEngine.register('false_belief', async function(container, config = {}) {
  const nTrials = config.trials || 8;

  await showInstructions(
    container,
    'False Belief Task',
    'You will read short stories about people and their beliefs.\n\n' +
    'For each story, answer the question about what a character believes.\n' +
    'Select the answer you think is correct.',
    'Start'
  );

  const trials = [];
  const vignettes = shuffle(FALSE_BELIEF_VIGNETTES).slice(0, nTrials);

  for (let i = 0; i < vignettes.length; i++) {
    const trial = await runFalseBeliefTrial(container, i, vignettes.length, vignettes[i]);
    trials.push(trial);
  }

  return trials;
});

function runFalseBeliefTrial(container, idx, total, vignette) {
  return new Promise((resolve) => {
    const area = el('div', { class: 'card task-stimulus-card' });
    container.appendChild(area);

    area.appendChild(el('h3', { text: 'Story ' + (idx + 1) + ' of ' + total }));
    area.appendChild(el('p', { class: 'task-story', text: vignette.story }));

    const options = shuffle(vignette.options.map((text, i) => ({ text, isCorrect: i === vignette.correct })));

    const fieldset = el('fieldset', { class: 'task-fb-options' });
    fieldset.style.border = 'none';
    fieldset.style.padding = '0';

    const legend = el('legend', { text: 'Select your answer:' });
    fieldset.appendChild(legend);

    options.forEach((opt, oi) => {
      const label = el('label', { class: 'task-fb-option' });
      const radio = el('input', {
        attrs: { type: 'radio', name: 'fb_' + idx, value: String(oi) }
      });
      label.appendChild(radio);
      label.appendChild(el('span', { text: opt.text }));
      fieldset.appendChild(label);
    });

    area.appendChild(fieldset);

    const btn = el('button', { class: 'primary magic-border', text: 'Submit answer' });
    btn.disabled = true;

    fieldset.addEventListener('change', () => { btn.disabled = false; });

    btn.addEventListener('click', () => {
      const selected = fieldset.querySelector('input:checked');
      if (!selected) return;
      const opt = options[Number(selected.value)];
      area.replaceChildren();
      resolve({ correct: opt.isCorrect });
    });

    area.appendChild(btn);
  });
}

/* ------------------------------------------------------- loneliness_ucla */

const UCLA_ITEMS = [
  'How often do you feel that you lack companionship?',
  'How often do you feel left out?',
  'How often do you feel isolated from others?',
  'How often do you feel that you are "in tune" with the people around you?',
  'How often do you feel that there are people you can talk to?',
  'How often do you feel that there are people you can turn to?',
  'How often do you feel that there are people who really understand you?',
  'How often do you feel that there are people with whom you share common interests?',
  'How often do you feel that there is no one you can turn to?',
  'How often do you feel that your relationships with others are not meaningful?',
  'How often do you feel that you are no longer close to anyone?',
  'How often do you feel that your interests and ideas are not shared by those around you?',
  'How often do you feel that you are an outgoing person?',
  'How often do you feel that there are people who really understand you?',
  'How often do you feel that you are close to other people?',
  'How often do you feel that there are people you can talk to?',
  'How often do you feel that there are people you can turn to?',
  'How often do you feel that you lack companionship?',
  'How often do you feel left out?',
  'How often do you feel isolated from others?'
];

const UCLA_LABELS = ['Never', 'Rarely', 'Sometimes', 'Often'];

TaskEngine.register('loneliness_ucla', async function(container, config = {}) {
  const nTrials = config.trials || 20;

  await showInstructions(
    container,
    'UCLA Loneliness Scale',
    'Below are statements about how people sometimes feel.\n\n' +
    'For each statement, indicate how often you feel the way described.\n' +
    'There are no right or wrong answers.',
    'Start'
  );

  const trials = [];
  const items = UCLA_ITEMS.slice(0, nTrials);

  for (let i = 0; i < items.length; i++) {
    const trial = await runUCLATrial(container, i, items.length, items[i]);
    trials.push(trial);
  }

  return trials;
});

function runUCLATrial(container, idx, total, item) {
  return new Promise((resolve) => {
    const area = el('div', { class: 'card task-stimulus-card' });
    container.appendChild(area);

    area.appendChild(el('h3', { text: 'Item ' + (idx + 1) + ' of ' + total }));
    area.appendChild(el('p', { class: 'task-story', text: item }));

    const fieldset = el('fieldset', { class: 'task-ucla-options' });
    fieldset.style.border = 'none';
    fieldset.style.padding = '0';

    const legend = el('legend', { text: 'How often do you feel this way?' });
    fieldset.appendChild(legend);

    UCLA_LABELS.forEach((label, li) => {
      const optLabel = el('label', { class: 'task-ucla-option' });
      const radio = el('input', {
        attrs: { type: 'radio', name: 'ucla_' + idx, value: String(li + 1) }
      });
      optLabel.appendChild(radio);
      optLabel.appendChild(el('span', { text: label }));
      fieldset.appendChild(optLabel);
    });

    area.appendChild(fieldset);

    const btn = el('button', { class: 'primary magic-border', text: 'Next' });
    btn.disabled = true;

    fieldset.addEventListener('change', () => { btn.disabled = false; });

    btn.addEventListener('click', () => {
      const selected = fieldset.querySelector('input:checked');
      if (!selected) return;
      const score = Number(selected.value);
      area.replaceChildren();
      resolve({ score: score });
    });

    area.appendChild(btn);
  });
}

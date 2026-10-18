/// The signed-in shell: a bottom navigation bar over the five core surfaces.
library;

import 'package:flutter/material.dart';

import '../state/app_state.dart';
import 'mcp_screen.dart';
import 'onboarding_screen.dart';
import 'profile_screen.dart';
import 'settings_screen.dart';
import 'sources_screen.dart';
import 'study_screen.dart';
import 'today_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.state});

  final AppState state;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final pages = <Widget>[
      TodayScreen(state: state, onNavigate: (i) => setState(() => _index = i)),
      SourcesScreen(state: state),
      StudyScreen(state: state),
      ProfileScreen(state: state),
      _MoreScreen(state: state),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('CortexForge'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Center(
              child: Text(
                state.displayName,
                style: const TextStyle(
                  color: Color(0xFF8B98A5),
                  fontSize: 13,
                ),
              ),
            ),
          ),
        ],
      ),
      body: IndexedStack(index: _index, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.today_outlined),
            selectedIcon: Icon(Icons.today),
            label: 'Today',
          ),
          NavigationDestination(
            icon: Icon(Icons.folder_outlined),
            selectedIcon: Icon(Icons.folder),
            label: 'Sources',
          ),
          NavigationDestination(
            icon: Icon(Icons.school_outlined),
            selectedIcon: Icon(Icons.school),
            label: 'Study',
          ),
          NavigationDestination(
            icon: Icon(Icons.insights_outlined),
            selectedIcon: Icon(Icons.insights),
            label: 'Profile',
          ),
          NavigationDestination(
            icon: Icon(Icons.more_horiz),
            selectedIcon: Icon(Icons.more_horiz),
            label: 'More',
          ),
        ],
      ),
    );
  }
}

/// The fifth tab gathers the less-frequent surfaces: onboarding, integrations
/// and settings.
class _MoreScreen extends StatelessWidget {
  const _MoreScreen({required this.state});

  final AppState state;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _tile(
          context,
          icon: Icons.tune,
          title: 'Setup & onboarding',
          subtitle: 'The 13-probe first-run sequence',
          builder: (_) => OnboardingScreen(state: state),
        ),
        _tile(
          context,
          icon: Icons.hub_outlined,
          title: 'Integrations (MCP)',
          subtitle: 'Connect note systems and tools',
          builder: (_) => McpScreen(state: state),
        ),
        _tile(
          context,
          icon: Icons.settings_outlined,
          title: 'Settings',
          subtitle: 'Export, erase, sign out',
          builder: (_) => SettingsScreen(state: state),
        ),
      ],
    );
  }

  Widget _tile(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String subtitle,
    required WidgetBuilder builder,
  }) {
    return Card(
      child: ListTile(
        leading: Icon(icon),
        title: Text(title),
        subtitle: Text(
          subtitle,
          style: const TextStyle(color: Color(0xFF8B98A5), fontSize: 12),
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: builder),
        ),
      ),
    );
  }
}

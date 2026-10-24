import Flutter
import UIKit
import XCTest

/// Native-side coverage for the iOS runner.
///
/// The Dart suite (45 tests, `flutter test`) covers the client's logic and
/// widgets. These tests cover what only exists on this platform: that the
/// runner is wired up and that the bundle metadata the App Store reads is
/// present and correct.
final class RunnerTests: XCTestCase {

    /// The bundle ID must match Android's `applicationId` so the two builds
    /// are the same app. iOS forbids underscores in bundle identifiers, so
    /// the shared value avoids them.
    func testBundleIdentifierMatchesAndroid() {
        let ios = Bundle.main.bundleIdentifier
        XCTAssertEqual(ios, "com.cortexforge.cortexforge")
    }

    /// The user-facing name comes from CFBundleDisplayName; CFBundleName is the
    /// short name shown under the icon on older layouts.
    func testDisplayNamesAreNotTheRawPackageName() {
        let plist = Bundle.main.infoDictionary
        let displayName = plist?["CFBundleDisplayName"] as? String
        let bundleName = plist?["CFBundleName"] as? String
        XCTAssertEqual(displayName, "CortexForge")
        XCTAssertEqual(bundleName, "CortexForge")
    }

    /// The client talks to a loopback HTTP server. Without this exemption App
    /// Transport Security refuses the connection and the app cannot reach the
    /// server at all.
    func testLocalNetworkingIsPermittedByATS() {
        let ats = Bundle.main.infoDictionary?["NSAppTransportSecurity"]
            as? [String: Any]
        XCTAssertEqual(ats?["NSAllowsLocalNetworking"] as? Bool, true)
    }

    /// App Store Connect rejects uploads that do not declare the encryption
    /// answer; it must be present and false.
    func testEncryptionDeclarationIsPresent() {
        let plist = Bundle.main.infoDictionary
        XCTAssertEqual(plist?["ITSAppUsesNonExemptEncryption"] as? Bool, false)
    }

    /// The Flutter engine only runs once the view controller is installed; a
    /// missing root would leave a blank screen.
    func testRootViewControllerIsInstalled() {
        let root = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap { $0.windows }
            .first { $0.isKeyWindow }?
            .rootViewController
        XCTAssertNotNil(root)
    }
}

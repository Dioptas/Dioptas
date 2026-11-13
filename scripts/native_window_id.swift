import CoreGraphics
import Foundation

// Return only a window owned by this test's process. Never capture the desktop
// or another application when a native test window has already closed.
let pid = Int(CommandLine.arguments[1])!
let title = CommandLine.arguments.count > 2 ? CommandLine.arguments[2] : ""
let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
let matches = windows.filter { window in
    guard window[kCGWindowOwnerPID as String] as? Int == pid,
          window[kCGWindowLayer as String] as? Int == 0,
          let bounds = window[kCGWindowBounds as String] as? [String: Double],
          (bounds["Width"] ?? 0) > 100, (bounds["Height"] ?? 0) > 100 else { return false }
    return title.isEmpty || (window[kCGWindowName as String] as? String ?? "").contains(title)
}
guard let window = matches.first, let id = window[kCGWindowNumber as String] as? Int else {
    fputs("Test window is not available for capture\n", stderr)
    exit(1)
}
print(id)

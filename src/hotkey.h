#pragma once

#include <windows.h>

#include <vector>

namespace desktopnote {

// Stable identifiers for global hotkeys (carried in WM_HOTKEY's wParam).
enum class GlobalHotkey : int {
    NewNote = 0x01,
    ToggleAll = 0x02,
};

struct HotkeyBinding {
    GlobalHotkey action;
    UINT modifiers;
    UINT virtual_key;
};

// The default, documented global-hotkey contract. Pure function; deterministic.
const std::vector<HotkeyBinding>& DefaultHotkeyBindings();

// Thin wrappers over RegisterHotKey / UnregisterHotKey. `window` is forwarded
// unchanged; pass nullptr to bind the hotkey to the calling thread.
bool RegisterGlobalHotkey(HWND window, int id, UINT modifiers, UINT virtual_key);
bool UnregisterGlobalHotkey(HWND window, int id);

}  // namespace desktopnote

#include "hotkey.h"

namespace desktopnote {

const std::vector<HotkeyBinding>& DefaultHotkeyBindings() {
    static const std::vector<HotkeyBinding> bindings = {
        {GlobalHotkey::NewNote, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 'N'},
        {GlobalHotkey::ToggleAll, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 'H'},
    };
    return bindings;
}

bool RegisterGlobalHotkey(HWND window, int id, UINT modifiers, UINT virtual_key) {
    return RegisterHotKey(window, id, modifiers, virtual_key) != FALSE;
}

bool UnregisterGlobalHotkey(HWND window, int id) {
    return UnregisterHotKey(window, id) != FALSE;
}

}  // namespace desktopnote

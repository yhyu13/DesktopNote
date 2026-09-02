#include "app_state.h"
#include "base64.h"
#include "rich_edit_host.h"

#include <windows.h>
#include <d2d1.h>
#include <d2d1helper.h>
#include <objbase.h>
#include <richedit.h>

#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using namespace desktopnote;

void Check(bool condition, const char* expression, int line) {
    if (!condition) {
        throw std::runtime_error("line " + std::to_string(line) +
                                 " check failed: " + expression);
    }
}

#define CHECK(expression) Check(static_cast<bool>(expression), #expression, __LINE__)

class ComApartment final {
public:
    ComApartment() : result_(CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED)) {
        CHECK(SUCCEEDED(result_));
    }
    ~ComApartment() {
        if (SUCCEEDED(result_)) CoUninitialize();
    }

private:
    HRESULT result_{};
};

class Window final {
public:
    Window()
        : handle_(CreateWindowExW(0, L"STATIC", L"DesktopNote RichEdit test",
                                  WS_OVERLAPPED, 0, 0, 420, 240, nullptr, nullptr,
                                  GetModuleHandleW(nullptr), nullptr)) {
        CHECK(handle_ != nullptr);
    }
    ~Window() {
        if (handle_) DestroyWindow(handle_);
    }
    HWND Get() const { return handle_; }

private:
    HWND handle_ = nullptr;
};

void TestRichTextRoundTripAndDraw() {
    ComApartment apartment;
    Window first_window;
    Window second_window;

    Appearance appearance;
    appearance.font_family = L"Microsoft YaHei";
    appearance.font_size_dip = 16.0;
    appearance.font_color = 0x101010;
    appearance.background_color = 0xFFFFFF;

    int change_notifications = 0;
    RichEditHost first(first_window.Get(), [&change_notifications] { ++change_notifications; });
    first.SetBounds(RECT{0, 0, 420, 240});
    CHECK(first.Initialize(appearance));
    CHECK((GetWindowLongPtrW(first_window.Get(), GWL_STYLE) & WS_VSCROLL) == 0);

    const std::wstring initial_text = L"DesktopNote 中文 \U0001F600";
    first.ForwardMessage(WM_SETTEXT, 0, reinterpret_cast<LPARAM>(initial_text.c_str()));
    CHECK(first.PlainText() == initial_text);
    CHECK((GetWindowLongPtrW(first_window.Get(), GWL_STYLE) & WS_VSCROLL) == 0);

    first.ForwardMessage(EM_SETSEL, 0, 11);
    const int notifications_before_format = change_notifications;
    first.ApplyFontFamily(L"Microsoft YaHei");
    first.ApplyFontSize(20.0);
    first.ApplyFontColor(0xD32F2F);
    first.ApplyParagraphSpacing(6.0);
    CHECK(change_notifications >= notifications_before_format + 4);

    const std::wstring paragraphs = L"第一段\r\n第二段";
    first.ForwardMessage(WM_SETTEXT, 0, reinterpret_cast<LPARAM>(paragraphs.c_str()));
    CHARRANGE saved_selection{1, 3};
    first.ForwardMessage(EM_EXSETSEL, 0, reinterpret_cast<LPARAM>(&saved_selection));
    first.ApplyParagraphSpacing(6.0);
    CHARRANGE restored_selection{};
    first.ForwardMessage(EM_EXGETSEL, 0, reinterpret_cast<LPARAM>(&restored_selection));
    CHECK(restored_selection.cpMin == saved_selection.cpMin);
    CHECK(restored_selection.cpMax == saved_selection.cpMax);
    for (const LONG position : {0L, static_cast<LONG>(paragraphs.size() - 1)}) {
        CHARRANGE paragraph_selection{position, position};
        first.ForwardMessage(EM_EXSETSEL, 0, reinterpret_cast<LPARAM>(&paragraph_selection));
        PARAFORMAT2 format{};
        format.cbSize = sizeof(format);
        first.ForwardMessage(EM_GETPARAFORMAT, 0, reinterpret_cast<LPARAM>(&format));
        CHECK((format.dwMask & PFM_SPACEAFTER) != 0);
        CHECK(format.dySpaceAfter == 90);
    }

    first.ForwardMessage(WM_SETTEXT, 0, reinterpret_cast<LPARAM>(initial_text.c_str()));
    first.ForwardMessage(EM_SETSEL, 0, 11);
    first.ApplyFontColor(0xD32F2F);

    first.ForwardMessage(EM_SETSEL, static_cast<WPARAM>(-1), static_cast<LPARAM>(-1));
    const std::wstring suffix = L" 格式";
    first.ForwardMessage(EM_REPLACESEL, TRUE, reinterpret_cast<LPARAM>(suffix.c_str()));
    const std::wstring expected_text = initial_text + suffix;
    CHECK(first.PlainText() == expected_text);

    const auto saved_base64 = first.SaveRtfBase64();
    CHECK(saved_base64.has_value());
    CHECK(!saved_base64->empty());
    const auto saved_bytes = DecodeBase64(*saved_base64);
    const std::string saved_rtf(saved_bytes.begin(), saved_bytes.end());
    CHECK(saved_rtf.find("\\rtf") != std::string::npos);
    CHECK(saved_rtf.find("\\red211\\green47\\blue47") != std::string::npos);

    RichEditHost second(second_window.Get(), [] {});
    second.SetBounds(RECT{0, 0, 420, 240});
    CHECK(second.Initialize(appearance));
    CHECK(second.LoadRtfBase64(*saved_base64));
    CHECK(second.PlainText() == expected_text);

    ID2D1Factory* factory = nullptr;
    CHECK(SUCCEEDED(D2D1CreateFactory(D2D1_FACTORY_TYPE_SINGLE_THREADED, &factory)));

    ID2D1DCRenderTarget* render_target = nullptr;
    const auto properties = D2D1::RenderTargetProperties(
        D2D1_RENDER_TARGET_TYPE_DEFAULT,
        D2D1::PixelFormat(DXGI_FORMAT_B8G8R8A8_UNORM, D2D1_ALPHA_MODE_PREMULTIPLIED),
        96.0F, 96.0F);
    CHECK(SUCCEEDED(factory->CreateDCRenderTarget(&properties, &render_target)));

    BITMAPINFO bitmap_info{};
    bitmap_info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bitmap_info.bmiHeader.biWidth = 420;
    bitmap_info.bmiHeader.biHeight = -240;
    bitmap_info.bmiHeader.biPlanes = 1;
    bitmap_info.bmiHeader.biBitCount = 32;
    bitmap_info.bmiHeader.biCompression = BI_RGB;
    void* pixels = nullptr;
    HDC memory_dc = CreateCompatibleDC(nullptr);
    CHECK(memory_dc != nullptr);
    HBITMAP bitmap = CreateDIBSection(memory_dc, &bitmap_info, DIB_RGB_COLORS,
                                      &pixels, nullptr, 0);
    CHECK(bitmap != nullptr);
    HGDIOBJ previous_bitmap = SelectObject(memory_dc, bitmap);
    const RECT draw_bounds{0, 0, 420, 240};
    CHECK(SUCCEEDED(render_target->BindDC(memory_dc, &draw_bounds)));

    render_target->BeginDraw();
    render_target->Clear(D2D1::ColorF(0.0F, 0.0F, 0.0F, 0.0F));
    CHECK(SUCCEEDED(second.Draw(render_target)));
    CHECK(SUCCEEDED(render_target->EndDraw()));

    const auto* pixel_values = static_cast<const std::uint32_t*>(pixels);
    bool drew_pixels = false;
    for (std::size_t index = 0; index < 420U * 240U; ++index) {
        if (pixel_values[index] != 0) {
            drew_pixels = true;
            break;
        }
    }
    CHECK(drew_pixels);

    SelectObject(memory_dc, previous_bitmap);
    DeleteObject(bitmap);
    DeleteDC(memory_dc);
    render_target->Release();
    factory->Release();
}

void TestCaretAndTextShareDipSpace() {
    ComApartment apartment;
    Window window;

    Appearance appearance;
    appearance.font_family = L"Microsoft YaHei";
    appearance.font_size_dip = 16.0;
    appearance.font_color = 0x101010;
    appearance.background_color = 0xFFFFFF;

    int change_notifications = 0;
    RichEditHost host(window.Get(), [&change_notifications] { ++change_notifications; });
    // bounds_ is the RichEdit client rect and must be in DIPs (the D2D render
    // target's space). If it is given in pixels (the historical bug), the control
    // lays text out at a scale that diverges from the DIP caret, so at any DPI !=
    // 96 the caret drifts off the text. This DIP rect maps to the pixel box
    // {40,40,220,120} at 120 DPI (ratio 120/96 = 1.25) inside a 420x240 window.
    const RECT bounds_dip{32, 32, 176, 96};
    host.SetBounds(bounds_dip);
    CHECK(host.Initialize(appearance));

    // Long content that wraps and fills the box so overflow is observable.
    const std::wstring fill_text(800, L'中');
    host.ForwardMessage(WM_SETTEXT, 0, reinterpret_cast<LPARAM>(fill_text.c_str()));

    ID2D1Factory* factory = nullptr;
    CHECK(SUCCEEDED(D2D1CreateFactory(D2D1_FACTORY_TYPE_SINGLE_THREADED, &factory)));

    // Non-96 DPI render target: the DIP/pixel ratio is 120/96 = 1.25.
    const auto properties = D2D1::RenderTargetProperties(
        D2D1_RENDER_TARGET_TYPE_DEFAULT,
        D2D1::PixelFormat(DXGI_FORMAT_B8G8R8A8_UNORM, D2D1_ALPHA_MODE_PREMULTIPLIED),
        120.0F, 120.0F);
    ID2D1DCRenderTarget* render_target = nullptr;
    CHECK(SUCCEEDED(factory->CreateDCRenderTarget(&properties, &render_target)));

    BITMAPINFO bitmap_info{};
    bitmap_info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bitmap_info.bmiHeader.biWidth = 420;
    bitmap_info.bmiHeader.biHeight = -240;
    bitmap_info.bmiHeader.biPlanes = 1;
    bitmap_info.bmiHeader.biBitCount = 32;
    bitmap_info.bmiHeader.biCompression = BI_RGB;
    void* pixels = nullptr;
    HDC memory_dc = CreateCompatibleDC(nullptr);
    CHECK(memory_dc != nullptr);
    HBITMAP bitmap = CreateDIBSection(memory_dc, &bitmap_info, DIB_RGB_COLORS,
                                      &pixels, nullptr, 0);
    CHECK(bitmap != nullptr);
    HGDIOBJ previous_bitmap = SelectObject(memory_dc, bitmap);
    const RECT full_bounds{0, 0, 420, 240};
    CHECK(SUCCEEDED(render_target->BindDC(memory_dc, &full_bounds)));

    render_target->BeginDraw();
    render_target->Clear(D2D1::ColorF(0.0F, 0.0F, 0.0F, 0.0F));
    CHECK(SUCCEEDED(host.Draw(render_target)));
    CHECK(SUCCEEDED(render_target->EndDraw()));

    // The DIP bounds map back to pixels at 120 DPI (x 1.25):
    //   left = 32*1.25 = 40, top = 32*1.25 = 40, right = 176*1.25 = 220, bottom = 96*1.25 = 120.
    // Text must stay inside that pixel box. Any non-transparent pixel strictly
    // outside it means the text was scaled/misplaced against the DIP caret (the
    // drift bug). Small margin absorbs glyph antialiasing at the box edge.
    const auto* pixel_values = static_cast<const std::uint32_t*>(pixels);
    const int box_left = 40, box_top = 40, box_right = 220, box_bottom = 120;
    const int kMarginPx = 3;
    bool leaked = false;
    for (int y = 0; y < 240; ++y) {
        for (int x = 0; x < 420; ++x) {
            const std::uint32_t value = pixel_values[static_cast<std::size_t>(y) * 420U + x];
            if (value == 0) continue;
            const bool outside = x < box_left - kMarginPx ||
                                  x >= box_right + kMarginPx ||
                                  y < box_top - kMarginPx ||
                                  y >= box_bottom + kMarginPx;
            if (outside) {
                leaked = true;
                break;
            }
        }
        if (leaked) break;
    }
    CHECK(!leaked);

    // Also confirm the text actually rendered (it is not just empty).
    bool drew_pixels = false;
    for (std::size_t index = 0; index < 420U * 240U; ++index) {
        if (pixel_values[index] != 0) {
            drew_pixels = true;
            break;
        }
    }
    CHECK(drew_pixels);

    SelectObject(memory_dc, previous_bitmap);
    DeleteObject(bitmap);
    DeleteDC(memory_dc);
    render_target->Release();
    factory->Release();
}

void TestBoldItalicUnderlineAndCounts() {
    ComApartment apartment;
    Window window;

    Appearance appearance;
    appearance.font_family = L"Microsoft YaHei";
    appearance.font_size_dip = 16.0;
    appearance.font_color = 0x101010;
    appearance.background_color = 0xFFFFFF;

    RichEditHost host(window.Get(), [] {});
    host.SetBounds(RECT{0, 0, 420, 240});
    CHECK(host.Initialize(appearance));

    const std::wstring text = L"Hello world 你好世界";
    host.ForwardMessage(WM_SETTEXT, 0, reinterpret_cast<LPARAM>(text.c_str()));

    // Word / char count (CJK-aware): "Hello"(1) "world"(1) + 4 ideographs = 6 words.
    CHECK(host.CharacterCount() == text.size());
    CHECK(host.WordCount() == 6);

    // Bold toggle on a selected range, then off.
    host.ForwardMessage(EM_SETSEL, 0, 5);  // select "Hello"
    host.ApplyBold();
    CHARFORMAT2W format{};
    format.cbSize = sizeof(format);
    host.ForwardMessage(EM_GETCHARFORMAT, SCF_SELECTION,
                        reinterpret_cast<LPARAM>(&format));
    CHECK((format.dwEffects & CFE_BOLD) != 0);

    host.ApplyBold();
    host.ForwardMessage(EM_GETCHARFORMAT, SCF_SELECTION,
                        reinterpret_cast<LPARAM>(&format));
    CHECK((format.dwEffects & CFE_BOLD) == 0);

    // Italic and underline apply to the selected range.
    host.ApplyItalic();
    host.ForwardMessage(EM_GETCHARFORMAT, SCF_SELECTION,
                        reinterpret_cast<LPARAM>(&format));
    CHECK((format.dwEffects & CFE_ITALIC) != 0);

    host.ApplyUnderline();
    host.ForwardMessage(EM_GETCHARFORMAT, SCF_SELECTION,
                        reinterpret_cast<LPARAM>(&format));
    CHECK((format.dwEffects & CFE_UNDERLINE) != 0);

    // Empty note has zero words / zero chars.
    host.ForwardMessage(WM_SETTEXT, 0, reinterpret_cast<LPARAM>(L""));
    CHECK(host.CharacterCount() == 0);
    CHECK(host.WordCount() == 0);
}

}  // namespace

int main() {
    try {
        TestRichTextRoundTripAndDraw();
        TestCaretAndTextShareDipSpace();
        TestBoldItalicUnderlineAndCounts();
        std::cout << "[PASS] Windowless RichEdit RTF round-trip and Direct2D draw\n";
        std::cout << "[PASS] Caret/text share a single DIP space (no drift)\n";
        std::cout << "[PASS] Bold/Italic/Underline toggles + CJK word count\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "[FAIL] " << error.what() << '\n';
        return 1;
    }
}

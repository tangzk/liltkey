#include "linebuffer.h"

#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

void require(bool condition, const char *message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

void test_fragmented_jsonl_is_reassembled() {
    voiceinput::LineBuffer buffer(32);
    auto first = buffer.feed("{\"a\":1}\n{\"b\"");
    require(!first.overflow, "bounded input should not overflow");
    require(first.lines.size() == 1 && first.lines[0] == R"({"a":1})",
            "complete first line should be emitted");
    auto second = buffer.feed(":2}\n");
    require(!second.overflow, "second fragment should stay bounded");
    require(second.lines.size() == 1 && second.lines[0] == R"({"b":2})",
            "fragmented second line should be reassembled");
}

void test_overlong_unterminated_line_is_rejected() {
    voiceinput::LineBuffer buffer(8);
    auto result = buffer.feed("123456789");
    require(result.overflow, "line beyond the byte limit must overflow");
    require(result.lines.empty(), "overlong line must not be delivered");
}

} // namespace

int main() {
    try {
        test_fragmented_jsonl_is_reassembled();
        test_overlong_unterminated_line_is_rejected();
    } catch (const std::exception &error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
    std::cout << "plugin buffer tests passed\n";
    return EXIT_SUCCESS;
}

#pragma once
#include <array>
#include <cstdint>
#include <string>

namespace calckey {
enum class Error { none, divide_zero, overflow };
struct Decimal {
    uint64_t coefficient = 0;
    int exponent = 0;
    bool negative = false;
    Error error = Error::none;
    static Decimal parse(const std::string&);
    static Decimal calculate(Decimal, char, Decimal);
    std::string text() const;
    Decimal for_display() const;
    std::string display_text() const;
};
class Calculator {
public:
    void key(char);
    void clear();
    std::string text() const;
    char operation() const { return pending_; }
private:
    Decimal value_{}, accumulator_{}, repeat_operand_{};
    std::string entry_ = "0";
    char pending_ = 0, repeat_operation_ = 0;
    bool entering_ = false, fresh_ = true;
    void refresh();
};
class Debouncer {
public:
    uint32_t update(uint32_t raw, uint32_t now_ms);
private:
    uint32_t candidates_ = 0, stable_ = 0;
    std::array<uint32_t,20> since_{};
};
enum class Mode { calculator, keyboard };
using Report = std::array<uint8_t,6>;
class Application {
public:
    void mount();
    void unmount();
    void suspend();
    void resume();
    void sample(uint32_t stable, uint32_t raw, uint32_t now_ms);
    bool next_report(Report&) const;
    void report_sent();
    void recover_reports();
    Mode mode() const { return mode_; }
    bool mounted() const { return mounted_; }
    bool suspended() const { return suspended_; }
    Calculator calculator;
    static uint8_t hid_code(unsigned key);
private:
    Mode mode_ = Mode::calculator;
    bool mounted_ = false, suspended_ = false, barrier_ = true, repeating_ = false;
    uint32_t previous_ = 0, repeat_at_ = 0;
    std::array<Report,32> reports_{};
    unsigned front_ = 0, count_ = 0;
    Report desired_{};
    void boundary();
    void enqueue(const Report&);
};
}

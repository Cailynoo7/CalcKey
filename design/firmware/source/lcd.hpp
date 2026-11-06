#pragma once
#include "core.hpp"
#include <array>
#include <string>

namespace calckey {
// One byte per 4-bit HT1621 RAM address. Upper bits are always zero.
using LcdRam=std::array<uint8_t,32>;
class Gdm0103 {
public:
    static LcdRam encode(const std::string& text);
};
class Lcd {
public:
    void init();
    void task(uint32_t now_ms,const Application&,bool numlock);
private:
    LcdRam frame_{},shown_{};
    bool configured_=false, have_shown_=false, transfer_=false;
    bool awake_=false, ui_started_=false, banner_=false;
    Mode previous_mode_=Mode::calculator;
    std::string previous_value_;
    unsigned config_step_=0, offset_=0, sleep_step_=0;
    uint32_t ready_at_=0, resync_at_=0, banner_at_=0;
    void bit(bool);
    void msb(unsigned,unsigned);
    void begin();
    void end();
    void command(uint8_t);
    void write_chunk();
    LcdRam desired(uint32_t,const Application&,bool);
};
}

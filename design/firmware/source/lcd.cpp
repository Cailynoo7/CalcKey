#include "lcd.hpp"
#include "board_config.hpp"
#include "hardware/gpio.h"
#include "pico/time.h"
#include <algorithm>

namespace calckey {
namespace {
// GDM0103 manual PDF pp8,12: physical digits 1..8, left to right.
// Rows are A,B,C,D,E,F,G; entries encode 4*RAM_address + D_bit.
constexpr uint8_t segments[8][7]={
    {4,5,6,3,2,0,1}, {12,13,14,11,10,8,9},
    {20,21,22,19,18,16,17}, {28,29,30,27,26,24,25},
    {56,57,58,63,62,60,61}, {48,49,50,55,54,52,53},
    {40,41,42,47,46,44,45}, {32,33,34,39,38,36,37}
};
// CP1,CP2,CP3,CP4,CP7,CP8,CP9; digit 8 has NO decimal point.
constexpr uint8_t points[7]={7,15,23,31,59,51,43};
// A..G mask. CP5/CP6 are the central colon, left off in this UI.
int glyph(char c) {
    constexpr uint8_t digits[10]={0x3f,0x06,0x5b,0x4f,0x66,0x6d,0x7d,0x07,0x7f,0x6f};
    if(c>='0'&&c<='9') return digits[c-'0'];
    switch(c) {
    case ' ':return 0; case '-':return 0x40;
    case 'P':return 0x73; case 'C':return 0x39;
    case 'A':return 0x77; case 'L':return 0x38;
    case 'E':return 0x79; case 'r':return 0x50;
    default:return -1;
    }
}
bool due(uint32_t now,uint32_t deadline) { return int32_t(now-deadline)>=0; }
}
LcdRam Gdm0103::encode(const std::string& input) {
    std::string text=input;
    unsigned cells=0, dots=0;
    bool valid=!text.empty();
    for(unsigned i=0;i<text.size();++i) {
        char c=text[i];
        if(c=='.') {
            ++dots;
            if(!i||text[i-1]<'0'||text[i-1]>'9') valid=false;
        } else { ++cells; if(glyph(c)<0) valid=false; }
    }
    bool trailing=!text.empty()&&text.back()=='.';
    if(!valid||dots>1||cells+(trailing?1:0)>8) {
        text="Err";cells=3;trailing=false;
    }
    LcdRam ram{};
    unsigned pos=8-cells-(trailing?1:0);
    auto set=[&](uint8_t index) { ram[index/4]|=1u<<(index%4); };
    for(char c:text) {
        if(c=='.') { set(points[pos-1]); continue; }
        const unsigned mask=unsigned(glyph(c));
        for(unsigned segment=0;segment<7;++segment)
            if(mask&(1u<<segment)) set(segments[pos][segment]);
        ++pos;
    }
    return ram;
}
void Lcd::init() {
    for(auto pin:{lcd_cs,lcd_wr,lcd_data}) {
        gpio_init(pin); gpio_put(pin,pin!=lcd_data); gpio_set_dir(pin,GPIO_OUT);
        gpio_disable_pulls(pin);
    }
    // Do not block USB startup while the LCD supply stabilises.
    ready_at_=uint32_t(time_us_64()/1000)+lcd_power_up_ms;
}
void Lcd::bit(bool value) {
    gpio_put(lcd_wr,0); gpio_put(lcd_data,value);
    busy_wait_us_32(lcd_half_clock_us);
    gpio_put(lcd_wr,1); busy_wait_us_32(lcd_half_clock_us);
}
void Lcd::msb(unsigned value,unsigned count) {
    while(count) bit((value>>(--count))&1u);
}
void Lcd::begin() {
    gpio_put(lcd_cs,1); busy_wait_us_32(lcd_half_clock_us);
    gpio_put(lcd_cs,0); busy_wait_us_32(lcd_half_clock_us);
}
void Lcd::end() { gpio_put(lcd_cs,1); busy_wait_us_32(lcd_half_clock_us); }
void Lcd::command(uint8_t value) {
    begin();msb(0b100,3);msb(value,8);bit(0);end(); // final don't-care bit
}
void Lcd::write_chunk() {
    begin();msb(0b101,3);msb(offset_,6); // A5..A0 first
    unsigned count=std::min<unsigned>(lcd_chunk_nibbles,frame_.size()-offset_);
    for(unsigned i=0;i<count;++i) {
        uint8_t nibble=frame_[offset_++];
        for(unsigned b=0;b<4;++b) bit((nibble>>b)&1u); // D0..D3, LSB first
    }
    end();
    if(offset_==frame_.size()) { shown_=frame_;have_shown_=true;transfer_=false; }
}
LcdRam Lcd::desired(uint32_t now,const Application& app,bool numlock) {
    std::string value=app.calculator.text();
    if(!ui_started_||app.mode()!=previous_mode_) {
        banner_=ui_started_||app.mode()==Mode::keyboard||value=="0";
        ui_started_=true;previous_mode_=app.mode();banner_at_=now;
        previous_value_=value;
    }
    if(value!=previous_value_) { banner_=false;previous_value_=value; }
    if(banner_&&uint32_t(now-banner_at_)>=lcd_banner_ms) banner_=false;
    if(banner_) return Gdm0103::encode(app.mode()==Mode::calculator?"CALC":"PC");
    return Gdm0103::encode(app.mode()==Mode::calculator?value:(numlock?"PC 1":"PC 0"));
}
void Lcd::task(uint32_t now,const Application& app,bool numlock) {
    if(app.suspended()) {
        transfer_=false;configured_=false;config_step_=0;have_shown_=false;
        banner_=false;ui_started_=false;awake_=false;
        if(sleep_step_==0) { command(0x02);++sleep_step_; }
        else if(sleep_step_==1) { command(0x00);++sleep_step_; }
        return;
    }
    if(sleep_step_) { sleep_step_=0;ready_at_=now+lcd_power_up_ms; }
    if(!due(now,ready_at_)) return;
    if(!configured_) {
        // Holtek Rev3.40 pp16-17. SYS DIS/LCD OFF only on cold start/resume;
        // periodic write-only resync does not blank a healthy display.
        static constexpr uint8_t commands[]={0x00,0x02,0x18,0x29,0x05,0x04,0x08,0x80,0xe3,0x01};
        command(commands[config_step_++]);
        if(config_step_==sizeof(commands)) {
            configured_=true;have_shown_=false;transfer_=false;resync_at_=now+lcd_resync_ms;
        }
        return;
    }
    LcdRam next=desired(now,app,numlock);
    // Finish each snapshot before accepting another one: rapid input cannot
    // starve the right half of the panel or leave the colon at random RAM data.
    if(transfer_) { write_chunk();return; }
    if(have_shown_&&!awake_) { command(0x03);awake_=true;return; } // never starve first enable
    if(!have_shown_||next!=shown_) { frame_=next;offset_=0;transfer_=true;write_chunk();return; }
    if(due(now,resync_at_)) { configured_=false;config_step_=2;awake_=false; }
    // No ACK/readback exists on this write-only wiring. Never claim detection.
}
}

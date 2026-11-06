#include "core.hpp"
#include "board_config.hpp"
#include "lcd.hpp"
#include "pico/stdlib.h"
#include "tusb.h"
#include <algorithm>
#include <cstring>

static calckey::Application app;
static calckey::Debouncer debounce;
static calckey::Lcd display;
static calckey::Report last_sent{};
static bool numlock=false;
static uint32_t idle_period=0,last_report_ms=0;

static void matrix_init() {
    for(auto pin:calckey::row_pins) { gpio_init(pin); gpio_put(pin,0); gpio_disable_pulls(pin); gpio_set_dir(pin,GPIO_IN); }
    for(auto pin:calckey::column_pins) { gpio_init(pin); gpio_set_dir(pin,GPIO_IN); gpio_disable_pulls(pin); }
}
static uint32_t matrix_scan() {
    uint32_t pressed=0;
    for(unsigned r=0;r<5;++r) {
        auto pin=calckey::row_pins[r]; gpio_set_dir(pin,GPIO_OUT); busy_wait_us_32(20);
        for(unsigned c=0;c<4;++c) if(!gpio_get(calckey::column_pins[c])) pressed|=1u<<(r*4+c);
        gpio_set_dir(pin,GPIO_IN); // unselected rows are high impedance, never driven high
    }
    return pressed;
}
extern "C" {
void tud_mount_cb() { app.mount(); last_sent={}; numlock=false; idle_period=0; }
void tud_umount_cb() { app.unmount(); last_sent={}; numlock=false; idle_period=0; }
void tud_suspend_cb(bool remote_wakeup_en) { (void)remote_wakeup_en; app.suspend(); }
void tud_resume_cb() { app.resume(); }
uint16_t tud_hid_get_report_cb(uint8_t instance,uint8_t id,hid_report_type_t type,uint8_t* buffer,uint16_t length) {
    (void)instance;
    if(id || type!=HID_REPORT_TYPE_INPUT) return 0;
    uint8_t report[8]={0,0}; std::memcpy(report+2,last_sent.data(),6);
    auto n=std::min<uint16_t>(length,sizeof(report)); std::memcpy(buffer,report,n); return n;
}
void tud_hid_set_report_cb(uint8_t instance,uint8_t id,hid_report_type_t type,const uint8_t* buffer,uint16_t length) {
    (void)instance; if(id==0&&type==HID_REPORT_TYPE_OUTPUT&&length) numlock=(buffer[0]&KEYBOARD_LED_NUMLOCK)!=0;
}
bool tud_hid_set_idle_cb(uint8_t instance,uint8_t rate) { (void)instance; idle_period=uint32_t(rate)*4; return true; }
void tud_hid_report_failed_cb(uint8_t instance,hid_report_type_t type,const uint8_t* report,uint16_t length) {
    (void)instance;(void)type;(void)report;(void)length; app.recover_reports();
}
}
int main() {
    matrix_init(); display.init(); tusb_init();
    uint64_t next_scan=time_us_64();
    while(true) {
        tud_task();
        uint64_t now_us=time_us_64(); uint32_t now=uint32_t(now_us/1000);
        if(now_us>=next_scan) {
            next_scan=now_us+calckey::matrix_interval_us;
            // Preserve release debounce during suspend but never drive row outputs.
            uint32_t raw=app.suspended()?0:matrix_scan();
            app.sample(debounce.update(raw,now),raw,now);
        }
        calckey::Report report;
        if(tud_hid_ready()) {
            bool queued=app.next_report(report);
            bool idle=!app.suspended()&&app.mounted()&&idle_period&&uint32_t(now-last_report_ms)>=idle_period;
            if(queued||idle) {
                if(!queued) report=last_sent;
                if(tud_hid_keyboard_report(0,0,report.data())) { last_sent=report; last_report_ms=now; if(queued) app.report_sent(); }
            }
        }
        // At most one LCD packet (25 clocks, 265us nominal) per task.
        // Keep USB servicing and the next 2ms matrix scan ahead of display work.
        if(int64_t(next_scan-time_us_64())>600) display.task(now,app,numlock);
        tight_loop_contents();
    }
}

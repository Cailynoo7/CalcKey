#include "tusb.h"
#include "pico/unique_id.h"
#include "board_config.hpp"
#include <algorithm>
#include <cstring>

static const uint8_t report_descriptor[]={TUD_HID_REPORT_DESC_KEYBOARD()};
static const tusb_desc_device_t device_descriptor={
    sizeof(tusb_desc_device_t),TUSB_DESC_DEVICE,0x0200,0,0,0,64,
    calckey::usb_vid,calckey::usb_pid,0x0100,1,2,3,1
};
static const uint8_t configuration_descriptor[]={
    TUD_CONFIG_DESCRIPTOR(1,1,0,TUD_CONFIG_DESC_LEN+TUD_HID_DESC_LEN,0,100),
    TUD_HID_DESCRIPTOR(0,4,HID_ITF_PROTOCOL_KEYBOARD,sizeof(report_descriptor),0x81,16,2)
};
extern "C" {
const uint8_t* tud_descriptor_device_cb() { return reinterpret_cast<const uint8_t*>(&device_descriptor); }
const uint8_t* tud_descriptor_configuration_cb(uint8_t index) { (void)index; return configuration_descriptor; }
const uint8_t* tud_hid_descriptor_report_cb(uint8_t instance) { (void)instance; return report_descriptor; }
const uint16_t* tud_descriptor_string_cb(uint8_t index,uint16_t language) {
    (void)language;
    static uint16_t out[33];
    if(index==0) { out[0]=(TUSB_DESC_STRING<<8)|4; out[1]=0x0409; return out; }
    char serial[PICO_UNIQUE_BOARD_ID_SIZE_BYTES*2+1];
    pico_get_unique_board_id_string(serial,sizeof(serial));
    const char* text=nullptr;
    switch(index) {
    case 1:text="CalcKey Prototype";break;
    case 2:text="CalcKey Dual Mode";break;
    case 3:text=serial;break;
    case 4:text="Numeric Keypad";break;
    default:return nullptr;
    }
    unsigned n=std::min<unsigned>(std::strlen(text),32);
    for(unsigned i=0;i<n;++i) out[i+1]=uint8_t(text[i]);
    out[0]=(TUSB_DESC_STRING<<8)|(2*n+2); return out;
}
}

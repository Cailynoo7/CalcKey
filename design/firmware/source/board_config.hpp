#pragma once
#include <array>
#include <cstdint>
namespace calckey {
// Pin evidence: enclosure wiring.json; Pico RP-008299-DS p5;
// GDM0103 manual PDF p8 (P1 /CS, P2 /WR, P3 DATA).
inline constexpr std::array<unsigned,5> row_pins={2,3,4,5,6};
inline constexpr std::array<unsigned,4> column_pins={7,8,9,10};
inline constexpr unsigned lcd_data=0, lcd_wr=1, lcd_cs=11;
inline constexpr uint32_t matrix_interval_us=2000;
inline constexpr uint32_t lcd_half_clock_us=5, lcd_power_up_ms=50;
inline constexpr uint32_t lcd_resync_ms=5000, lcd_banner_ms=800;
inline constexpr unsigned lcd_chunk_nibbles=4;
static_assert(lcd_cs!=lcd_data && lcd_cs!=lcd_wr && lcd_data!=lcd_wr);
inline constexpr unsigned usb_vid=0xcafe, usb_pid=0x2350; // prototype IDs
}

#include "lcd.hpp"
#include "board_config.hpp"
#include "hardware/gpio.h"
#include <algorithm>
#include <array>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>
using namespace calckey;
static unsigned checks=0;
static void check(bool ok,const char* name) { ++checks;if(!ok) {std::cerr<<"FAIL "<<name<<'\n';std::exit(1);} }
static uint64_t clock_us=0,cs_at=0,wr_at=0,low_at=0,data_at=0;
static std::array<bool,32> levels{},directions{};
static std::vector<int> bits;
static std::vector<unsigned> commands;
static LcdRam memory{};
static uint32_t written=0;
static bool enabled=false,oscillator=false,normal=false,bias=false,rc=false;
static unsigned transactions=0,writes=0;
static unsigned read_msb(unsigned at,unsigned n) {
    unsigned result=0;for(unsigned i=0;i<n;++i)result=(result<<1)|unsigned(bits.at(at+i));return result;
}
static void packet() {
    ++transactions;
    unsigned id=read_msb(0,3);
    if(id==4) {
        check(bits.size()==12&&bits.back()==0,"command: 100 + eight MSB bits + don't-care");
        unsigned command=read_msb(3,8);commands.push_back(command);
        switch(command) {
        case 0x00:oscillator=false;enabled=false;written=0;break; // require fresh writes after sleep/reset
        case 0x01:oscillator=true;break;
        case 0x02:enabled=false;break;
        case 0x03:check(written==0xffffffffu,"all 32 RAM addresses written before LCD ON");enabled=true;break;
        case 0x18:rc=true;break;case 0x29:bias=true;break;case 0xe3:normal=true;break;
        case 0x04:case 0x05:case 0x08:case 0x80:break;
        default:check(false,"unexpected/unsafe controller command");
        }
    } else {
        check(id==5,"write ID is 101");
        check(bits.size()>9&&(bits.size()-9)%4==0,"RAM write has full nibbles");
        check(bits.size()<=25,"maximum four nibbles per task");
        unsigned address=read_msb(3,6); // address MSB first
        for(unsigned i=9;i<bits.size();i+=4) {
            check(address<32,"RAM address in range");
            unsigned nibble=0;for(unsigned b=0;b<4;++b)nibble|=unsigned(bits[i+b])<<b; // data LSB first
            memory[address]=nibble;written|=1u<<address;++address;
        }
        ++writes;
    }
}
uint64_t time_us_64() { return clock_us; }
void busy_wait_us_32(uint32_t us) { check(us>=5,"conservative delay at 3.3V");clock_us+=us; }
void gpio_init(unsigned pin) { check(pin==0||pin==1||pin==11,"LCD touches only current wiring GPIOs");levels.at(pin)=false; }
void gpio_set_dir(unsigned pin,bool output) { directions.at(pin)=output; }
void gpio_disable_pulls(unsigned pin) { check(pin==0||pin==1||pin==11,"no matrix pin reconfiguration"); }
void gpio_put(unsigned pin,bool value) {
    bool old=levels.at(pin);levels[pin]=value;
    if(pin==lcd_data&&old!=value)data_at=clock_us;
    if(pin==lcd_cs&&old!=value) {
        if(!value) {bits.clear();cs_at=clock_us;}
        else if(!bits.empty()) {
            check(clock_us-wr_at>=5,"CS hold after last rising WR");packet();bits.clear();
        }
    }
    if(pin==lcd_wr&&!value&&old&&!levels[lcd_cs]) {
        if(!bits.empty()) check(clock_us-wr_at>=5&&clock_us-wr_at<=125,"active WR high pulse in timing bounds");
        low_at=clock_us;
    }
    if(pin==lcd_wr&&value&&!old&&!levels[lcd_cs]) {
        check(clock_us-low_at>=5&&clock_us-low_at<=125,"active WR low pulse in timing bounds");
        check(clock_us-cs_at>=5,"CS setup before first WR");
        check(clock_us-data_at>=5,"DATA setup before rising WR");
        check(directions[lcd_data]&&directions[lcd_wr]&&directions[lcd_cs],"three outputs configured");
        bits.push_back(levels[lcd_data]);wr_at=clock_us;
    }
}
// Independent physical readout from manual pp8/12, rather than calling the encoder.
static std::string visible(const LcdRam& ram) {
    std::string result;
    for(unsigned digit=0;digit<8;++digit) {
        unsigned abc,defg;
        if(digit<4) {abc=ram[2*digit+1];defg=ram[2*digit];}
        else {abc=ram[22-2*digit];defg=ram[23-2*digit];}
        unsigned mask=(abc&7)|((defg&8)?8:0)|((defg&4)?16:0)|((defg&1)?32:0)|((defg&2)?64:0);
        const std::array<unsigned,10> digits={63,6,91,79,102,109,125,7,127,111};
        char c='?';for(unsigned d=0;d<10;++d)if(mask==digits[d])c=char('0'+d);
        if(mask==0)c=' ';if(mask==64)c='-';if(mask==115)c='P';if(mask==57)c='C';
        if(mask==119)c='A';if(mask==56)c='L';if(mask==121)c='E';if(mask==80)c='r';
        result+=c;
        if(digit<7) {
            unsigned a=digit<4?2*digit+1:22-2*digit;
            if(ram[a]&8)result+='.';
        }
    }
    return result;
}
static void frame(const char* input,const char* expected) {
    auto ram=Gdm0103::encode(input);
    if(visible(ram)!=expected)std::cerr<<input<<" -> ["<<visible(ram)<<"] expected ["<<expected<<"]\n";
    check(visible(ram)==expected,"physical digits and decimal segments");
    check(ram[16]==0,"central colon CP5/CP6 off");
    check(std::all_of(ram.begin()+17,ram.end(),[](uint8_t v){return v==0;}),"unused RAM clear");
    check(std::all_of(ram.begin(),ram.end(),[](uint8_t v){return v<=15;}),"RAM values are nibbles");
}
static void tick(Lcd& lcd,Application& app,uint32_t now,bool numlock=false) {
    clock_us=uint64_t(now)*1000;
    auto start=clock_us;unsigned before=transactions;
    lcd.task(now,app,numlock);
    check(transactions-before<=1,"one bounded LCD transaction per task");
    check(clock_us-start<=265,"nominal GPIO wait budget <=265us");
    check(levels[lcd_cs]&&levels[lcd_wr],"CS/WR idle high after each task");
}
static void pump(Lcd& lcd,Application& app,uint32_t now,bool numlock=false) {
    for(unsigned i=0;i<32;++i)tick(lcd,app,now+i*2,numlock);
}
int main() {
    const LcdRam golden={0,6,14,3,10,7,3,6,7,15,7,0,5,15,5,11,0};
    check(Gdm0103::encode("12345678")==golden,"golden asymmetric digit-order frame from manual");
    frame("12345678","12345678");frame("-1234567","-1234567");frame("0","       0");
    frame("CALC","    CALC");frame("PC","      PC");frame("PC 1","    PC 1");
    frame("Err","     Err");frame("0.","      0. ");frame("12.","     12. ");
    frame("-0.","     -0. ");frame("0.0000001","0.0000001");
    frame("-0.000001","-0.000001");
    for(unsigned i=1;i<8;++i) {
        std::string s="12345678";s.insert(i,".");auto expected=golden;
        const unsigned point_addresses[7]={1,3,5,7,14,12,10};expected[point_addresses[i-1]]|=8;
        check(Gdm0103::encode(s)==expected,"all seven decimal positions use CP1..4,7..9");
    }
    for(char digit='0';digit<='9';++digit)for(unsigned pos=0;pos<8;++pos) {
        std::string s(8,' ');s[pos]=digit;frame(s.c_str(),s.c_str());
    }
    for(const char* bad:{"123456789","12345678.",".1","1..2","1E+9","+",""})frame(bad,"     Err");
    Application app;app.sample(0,0,0);Lcd lcd;lcd.init();
    for(unsigned i=0;i<50;i+=2)tick(lcd,app,i);
    check(transactions==0,"nonblocking 50ms power stabilization");
    pump(lcd,app,50);
    check(commands==std::vector<unsigned>{0,2,0x18,0x29,5,4,8,0x80,0xe3,1,3},"known startup configuration and final LCD ON");
    check(enabled&&oscillator&&rc&&bias&&normal,"1/3 bias, 4 COM, RC, normal mode");
    check(visible(memory)=="    CALC","power-only CALC banner");
    pump(lcd,app,1000);check(visible(memory)=="       0","startup banner expires");
    app.calculator.key('1');app.calculator.key('2');app.calculator.key('.');
    pump(lcd,app,1100);check(visible(memory)=="     12. ","typed trailing dot over actual GPIO packets");
    app.calculator.key('3');pump(lcd,app,1200);check(visible(memory)=="     12.3","fraction entry returns to right alignment");
    app.mount();pump(lcd,app,1300);check(visible(memory)=="      PC","USB enumerated PC banner");
    pump(lcd,app,2200);check(visible(memory)=="    PC 0","host NumLock off");
    pump(lcd,app,2300,true);check(visible(memory)=="    PC 1","host NumLock on");
    app.sample(0,0,2400);app.sample(1u<<16,1u<<16,2401);
    pump(lcd,app,2410);check(visible(memory)=="    CALC","Mode switches to local CALC");
    app.calculator.key('4');pump(lcd,app,2500);check(visible(memory)=="    12.34","input cancels mode banner immediately");
    app.calculator.key('/');app.calculator.key('0');app.calculator.key('=');
    pump(lcd,app,2600);check(visible(memory)=="     Err","division by zero over GPIO");
    app.calculator.clear();pump(lcd,app,2700);check(visible(memory)=="       0","AC clears error and stale points");
    app.suspend();tick(lcd,app,2800);check(!enabled,"suspend disables LCD first");
    tick(lcd,app,2802);check(!oscillator,"suspend disables oscillator next");
    unsigned before=transactions;pump(lcd,app,2900);check(before==transactions,"no repeated writes during suspend");
    app.resume();pump(lcd,app,3000);pump(lcd,app,3100);check(enabled&&oscillator,"resume reinitializes and redraws");
    // Simulate LCD-only power loss. With no ACK this is recovered by periodic resync.
    memory.fill(15);written=0;enabled=oscillator=rc=bias=normal=false;
    pump(lcd,app,9000);check(enabled&&oscillator&&rc&&bias&&normal,"periodic resync recovers LCD power loss");
    check(memory[16]==0&&memory[31]==0,"resync clears colon and unused RAM");
    // Constant changes must not starve initialization or right-side refresh.
    Lcd busy;app.unmount();app.calculator.clear();clock_us=10000000;busy.init();
    for(unsigned i=0;i<100;++i) {
        app.calculator.clear();app.calculator.key(char('1'+i%9));tick(busy,app,10050+i*2);
    }
    check(enabled,"continuous input cannot starve LCD ON");
    // Wrap the 32-bit millisecond clock around during banner and power-on wait.
    Lcd wrap;app.calculator.clear();clock_us=uint64_t(0xfffffff0u)*1000;wrap.init();
    before=transactions;tick(wrap,app,0xfffffffeu);tick(wrap,app,33);check(before==transactions,"power delay survives timer wrap");
    pump(wrap,app,34);pump(wrap,app,1000);check(visible(memory)=="       0","banner timing survives wrap");
    check(writes>20,"waveform emulator exercised RAM writes");
    std::cout<<"PASS "<<checks<<" LCD waveform, segment mapping and mode assertions\n";
}

#include "core.hpp"
#include <cstdlib>
#include <iostream>
#include <limits>

using namespace calckey;
static unsigned checks=0;
static void check(bool ok,const char* name) { ++checks; if(!ok) { std::cerr<<"FAIL: "<<name<<'\n'; std::exit(1); } }
static void sequence(const char* keys,const char* expected) {
    Calculator c; for(const char* p=keys;*p;++p) c.key(*p);
    if(c.text()!=expected) std::cerr<<keys<<": "<<c.text()<<" expected "<<expected<<'\n';
    check(c.text()==expected,keys);
}
static void drain(Application& a) { Report r; while(a.next_report(r)) a.report_sent(); }
int main() {
    sequence("12+34=","46"); sequence("7-10=","-3"); sequence("1.5*2=","3");
    sequence("8/4=","2"); sequence("0.1+0.2=","0.3"); sequence("0.3-0.2=","0.1");
    sequence("1/6=","0.1666667"); sequence("2/3=","0.6666667");
    sequence("1/8=","0.125"); sequence("-5+2=","-3"); sequence("2*-3=","-6");
    sequence("2+3*4=","20"); sequence("2+*3=","6"); sequence("2+3===","11");
    sequence("12B3=","13"); sequence("12.B3=","123"); sequence("123C","0");
    sequence("1/0=","Err"); sequence("1/0=C2+2=","4"); sequence("1/0=7=","7");
    sequence("99999999+1=","Err"); sequence("99999999*99999999=","Err");
    sequence("123456789=","12345678"); sequence("1..2=","1.2"); sequence("2+=","4");
    sequence("-12345678=","-1234567"); sequence("0.00000012","0.0000001");
    sequence("-0.0000012","-0.000001"); sequence("12345678.","12345678");
    sequence("12.","12."); sequence("-0.","-0.");
    sequence("99999999+1=2+2=","4"); sequence("99999999+1=C","0");
    sequence("9999999-99999999=","Err");
    sequence("1/6=*6=","1.0000002"); // subsequent step uses visible rounded result
    sequence("0.0000001/2=","0.0000001"); // positive midpoint rounds away from zero
    sequence("0.0000001/3=","0"); sequence("-0.000001/2=","-0.000001");
    sequence("-0.000001/3=","0");
    sequence("1/6===","0.0046296");
    check(Decimal::calculate(Decimal{1,99,false,Error::none},'*',Decimal::parse("10")).error==Error::overflow,"upper range");
    check(Decimal::calculate(Decimal{1,-99,false,Error::none},'/',Decimal::parse("10")).error==Error::overflow,"lower range");
    check(Decimal::calculate(Decimal::parse("-0"),'+',Decimal::parse("0")).text()=="0","normalize zero");
    Debouncer d;
    check(d.update(1,0)==0,"debounce start"); check(d.update(0,2)==0,"debounce bounce");
    check(d.update(1,3)==0&&d.update(1,7)==0,"requires five ms"); check(d.update(1,8)==1,"stable press");
    check(d.update(0,9)==1&&d.update(0,14)==0,"stable release");
    Debouncer wrap; wrap.update(1,0xfffffffd); check(wrap.update(1,2)==1,"timer wrap");
    Application a; Report r;
    a.sample(0,0,0); check(a.mode()==Mode::calculator,"charger calculator");
    a.sample(1u<<12,1u<<12,1); check(a.calculator.text()=="1","calculator input");
    a.mount(); check(a.mode()==Mode::keyboard&&a.next_report(r)&&r==Report{},"mount releases keys");drain(a);
    a.sample(1u<<12,1u<<12,2); check(!a.next_report(r),"held key on mount blocked");
    a.sample(0,0,3); a.sample(1u<<12,1u<<12,4); check(a.next_report(r)&&r[0]==0x59,"keypad one");drain(a);
    a.sample((1u<<12)|(1u<<16),(1u<<12)|(1u<<16),5);
    check(a.mode()==Mode::calculator&&a.next_report(r)&&r==Report{},"Mode emits all up");drain(a);
    a.sample(1u<<12,1u<<12,6); check(a.calculator.text()=="1","Mode suppresses held digit");
    a.sample(0,0,7); a.sample(1u<<16,1u<<16,8);drain(a);a.sample(0,0,9);
    check(a.mode()==Mode::keyboard,"Mode return");
    a.sample(1u<<4,1u<<4,10); a.sample(0,0,11);
    check(a.next_report(r)&&r[0]==0x5f,"backpressure preserves down");a.report_sent();
    check(a.next_report(r)&&r==Report{},"backpressure preserves up");drain(a);
    a.suspend();check(a.mode()==Mode::keyboard,"suspend keeps mode");check(!a.next_report(r),"suspend sends nothing");
    a.resume();check(a.next_report(r)&&r==Report{},"resume flushes all up");drain(a);a.sample(0,0,12);
    a.sample(0x7f,0x7f,13);check(a.next_report(r)&&r==Report{1,1,1,1,1,1},"seven key rollover");drain(a);
    a.sample(0,0,14);drain(a);
    a.sample(1u<<19,1u<<19,15);check(a.calculator.text()=="0"&&!a.next_report(r),"AC in keypad mode clears locally");
    a.sample(0,0,16);
    for(unsigned i=0;i<40;++i) a.sample(i%2?0:1u<<12,i%2?0:1u<<12,20+i);
    check(a.next_report(r)&&r==Report{},"queue overflow releases host");drain(a);
    a.unmount();check(a.mode()==Mode::calculator&&!a.next_report(r),"detach calculator");
    Application held;held.mount();drain(held);
    held.sample(0,1u<<12,0);held.sample(1u<<12,1u<<12,5);
    check(!held.next_report(r),"raw key present during mount keeps barrier");
    held.sample(0,0,10);held.sample(1u<<16,1u<<16,11);drain(held);held.sample(0,0,12);
    check(held.mode()==Mode::calculator,"enter local mode for suspend check");
    held.suspend();held.resume();check(held.mode()==Mode::calculator,"resume preserves local mode");
    Application repeat;repeat.sample(0,0,0);
    repeat.sample(1u<<12,1u<<12,1);repeat.sample(0,0,2);
    repeat.sample(1u<<13,1u<<13,3);repeat.sample(0,0,4);
    repeat.sample(1u<<14,1u<<14,5);repeat.sample(0,0,6);
    repeat.sample(1u<<3,1u<<3,7);check(repeat.calculator.text()=="12","backspace first edge");
    repeat.sample(1u<<3,1u<<3,506);check(repeat.calculator.text()=="12","backspace waits 500ms");
    repeat.sample(1u<<3,1u<<3,507);check(repeat.calculator.text()=="1","backspace first repeat");
    repeat.sample(1u<<3,1u<<3,587);check(repeat.calculator.text()=="0","backspace subsequent repeat");
    for(unsigned i=0;i<20;++i) check((Application::hid_code(i)!=0)==(i!=16&&i!=19),"HID map contains only host keys");
    std::cout<<"PASS "<<checks<<" core assertions\n";
}

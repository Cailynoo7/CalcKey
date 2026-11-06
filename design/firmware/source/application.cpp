#include "core.hpp"
#include <algorithm>

namespace calckey {
uint32_t Debouncer::update(uint32_t raw,uint32_t now) {
    raw&=0xfffff;
    for(unsigned i=0;i<20;++i) {
        uint32_t bit=1u<<i;
        if((raw^candidates_)&bit) { candidates_^=bit; since_[i]=now; }
        if(((stable_^candidates_)&bit) && uint32_t(now-since_[i])>=5) stable_^=bit;
    }
    return stable_;
}
uint8_t Application::hid_code(unsigned k) {
    static constexpr uint8_t codes[20]={0x53,0x54,0x55,0x2a,0x5f,0x60,0x61,0x56,0x5c,0x5d,0x5e,0x57,0x59,0x5a,0x5b,0x58,0,0x62,0x63,0};
    return k<20?codes[k]:0;
}
void Application::enqueue(const Report& r) {
    if(r==desired_) return;
    if(count_==reports_.size()) { boundary(); return; } // fail closed; require all keys up
    reports_[(front_+count_)%reports_.size()]=r; ++count_; desired_=r;
}
void Application::boundary() {
    barrier_=true; front_=0; count_=mounted_?1:0; desired_={}; reports_[0]={}; repeating_=false;
}
void Application::recover_reports() { boundary(); }
void Application::mount() { mounted_=true; suspended_=false; mode_=Mode::keyboard; boundary(); }
void Application::unmount() { mounted_=false; suspended_=false; mode_=Mode::calculator; boundary(); }
void Application::suspend() { suspended_=true; boundary(); }
void Application::resume() { suspended_=false; boundary(); }
bool Application::next_report(Report& r) const {
    if(!mounted_||suspended_||!count_) return false;
    r=reports_[front_]; return true;
}
void Application::report_sent() { if(count_) { front_=(front_+1)%reports_.size(); --count_; } }
void Application::sample(uint32_t stable,uint32_t raw,uint32_t now) {
    uint32_t pressed=stable&~previous_; previous_=stable;
    if(suspended_) return;
    if(barrier_) { if(!(stable|raw)) barrier_=false; return; }
    if(pressed&(1u<<16)) {
        if(mounted_) { mode_=mode_==Mode::keyboard?Mode::calculator:Mode::keyboard; boundary(); }
        return;
    }
    if(mode_==Mode::keyboard) {
        if(pressed&(1u<<19)) calculator.clear(); // AC is local-only even in keyboard mode
        Report r{}; unsigned n=0;
        for(unsigned i=0;i<20;++i) if((stable&(1u<<i))&&hid_code(i)) { if(n<6) r[n]=hid_code(i); ++n; }
        if(n>6) r.fill(1); // standard ErrorRollOver, never silently choose six keys
        enqueue(r); return;
    }
    static constexpr char actions[20]={0,'/','*','B','7','8','9','-','4','5','6','+','1','2','3','=',0,'0','.','C'};
    for(unsigned i=0;i<20;++i) if((pressed&(1u<<i))&&actions[i]) calculator.key(actions[i]);
    if(pressed&(1u<<3)) { repeat_at_=now+500; repeating_=true; }
    if(!(stable&(1u<<3))) repeating_=false;
    else if(repeating_ && int32_t(now-repeat_at_)>=0) { calculator.key('B'); repeat_at_=now+80; }
}
}

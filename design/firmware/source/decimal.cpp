#include "core.hpp"
#include <algorithm>
#include <array>

namespace calckey {
namespace {
using Big = std::array<uint8_t,240>;
int digits(const Big& a) { int n=240; while(n && !a[n-1]) --n; return n; }
Big big(uint64_t v, int shift=0) {
    Big a{};
    while(v && shift<240) { a[shift++]=v%10; v/=10; }
    return a;
}
Decimal rounded(const Big& a, int exponent, bool negative) {
    Decimal r; int n=digits(a);
    if(!n) return r;
    int cut=std::max(0,n-12);
    for(int i=n-1;i>=cut;--i) r.coefficient=r.coefficient*10+a[i];
    if(cut && a[cut-1]>=5) ++r.coefficient; // decimal half away from zero
    r.exponent=exponent+cut; r.negative=negative;
    while(r.coefficient%10==0) { r.coefficient/=10; ++r.exponent; }
    int order=r.exponent+int(std::to_string(r.coefficient).size())-1;
    if(order>99 || order<-99) r.error=Error::overflow;
    return r;
}
int compare(const Big& a,const Big& b) {
    for(int i=239;i>=0;--i) if(a[i]!=b[i]) return a[i]>b[i]?1:-1;
    return 0;
}
}
Decimal Decimal::parse(const std::string& s) {
    Big a{}; bool neg=false, fraction=false; int exp=0;
    for(char c:s) {
        if(c=='-') { neg=true; continue; }
        if(c=='.') { fraction=true; continue; }
        if(c<'0'||c>'9') continue;
        for(int i=239;i>0;--i) a[i]=a[i-1];
        a[0]=c-'0'; if(fraction) --exp;
    }
    return rounded(a,exp,neg);
}
Decimal Decimal::calculate(Decimal a,char op,Decimal b) {
    if(a.error!=Error::none) return a;
    if(b.error!=Error::none) return b;
    if(op=='/' && !b.coefficient) { Decimal e; e.error=Error::divide_zero; return e; }
    if(op=='*') {
        Big x=big(a.coefficient),y=big(b.coefficient),out{};
        for(int i=0;i<12;++i) {
            unsigned carry=0;
            for(int j=0;j<12 || carry;++j) {
                unsigned v=out[i+j]+carry+(j<12?x[i]*y[j]:0);
                out[i+j]=v%10; carry=v/10;
            }
        }
        return rounded(out,a.exponent+b.exponent,a.negative!=b.negative);
    }
    if(op=='/') {
        uint64_t quotient=a.coefficient/b.coefficient;
        uint64_t remainder=a.coefficient%b.coefficient;
        int exp=a.exponent-b.exponent;
        while(remainder && quotient<1000000000000ULL) {
            remainder*=10; quotient=quotient*10+remainder/b.coefficient;
            remainder%=b.coefficient; --exp;
        }
        return rounded(big(quotient),exp,a.negative!=b.negative);
    }
    if(op=='-') b.negative=!b.negative;
    int exp=std::min(a.exponent,b.exponent);
    Big x=big(a.coefficient,a.exponent-exp),y=big(b.coefficient,b.exponent-exp),out{};
    bool neg=a.negative;
    if(a.negative==b.negative) {
        unsigned carry=0;
        for(unsigned i=0;i<out.size();++i) { unsigned v=x[i]+y[i]+carry; out[i]=v%10; carry=v/10; }
    } else {
        if(compare(x,y)<0) { std::swap(x,y); neg=b.negative; }
        int borrow=0;
        for(unsigned i=0;i<out.size();++i) { int v=x[i]-y[i]-borrow; borrow=v<0; out[i]=v+(borrow?10:0); }
    }
    return rounded(out,exp,neg);
}
std::string Decimal::text() const {
    if(error==Error::divide_zero) return "DIV BY ZERO";
    if(error==Error::overflow) return "OVERFLOW";
    if(!coefficient) return "0";
    std::string s=std::to_string(coefficient),fixed;
    int point=int(s.size())+exponent;
    if(point<=0 && -point+int(s.size())+2<=18) fixed="0."+std::string(-point,'0')+s;
    else if(point>=int(s.size()) && point<=18) fixed=s+std::string(point-s.size(),'0');
    else if(point>0 && point<int(s.size())) fixed=s.substr(0,point)+"."+s.substr(point);
    if(!fixed.empty() && fixed.size()+(negative?1:0)<=18) return (negative?"-":"")+fixed;
    std::string mantissa=s.substr(0,1)+(s.size()>1?"."+s.substr(1):"");
    int e=exponent+int(s.size())-1;
    return (negative?"-":"")+mantissa+"E"+(e<0?"-":"+")+std::to_string(e<0?-e:e);
}
Decimal Decimal::for_display() const {
    Decimal r=*this;
    if(r.error!=Error::none) return r;
    if(!r.coefficient) return Decimal{};
    const int cells=8-(r.negative?1:0);
    int integer_digits=std::max(1,int(std::to_string(r.coefficient).size())+r.exponent);
    if(integer_digits>cells) { r.error=Error::overflow; return r; }
    // The leading zero, fractional zeros and minus all consume digit cells.
    // The decimal point is a separate physical segment, not a character cell.
    int cut=std::max(0,-(cells-integer_digits)-r.exponent);
    unsigned last=0;
    for(int i=0;i<cut;++i) { last=r.coefficient%10; r.coefficient/=10; }
    if(cut && last>=5) ++r.coefficient;
    r.exponent+=cut;
    if(!r.coefficient) return Decimal{};
    while(r.coefficient%10==0) { r.coefficient/=10; ++r.exponent; }
    integer_digits=std::max(1,int(std::to_string(r.coefficient).size())+r.exponent);
    if(integer_digits>cells) r.error=Error::overflow; // carry across the last cell
    return r;
}
std::string Decimal::display_text() const {
    Decimal r=for_display();
    return r.error==Error::none?r.text():"Err";
}
void Calculator::clear() { *this=Calculator{}; }
void Calculator::refresh() { value_=Decimal::parse(entry_); }
std::string Calculator::text() const { return entering_?entry_:value_.display_text(); }
void Calculator::key(char c) {
    if(c=='C') { clear(); return; }
    if(value_.error!=Error::none) { if((c>='0'&&c<='9')||c=='.') clear(); else return; }
    if((c>='0'&&c<='9')||c=='.') {
        if(!entering_) { entry_="0"; entering_=true; }
        repeat_operation_=0; fresh_=false;
        auto cells=unsigned(std::count_if(entry_.begin(),entry_.end(),[](char v) { return v!='.'; }));
        if(c=='.') {
            // GDM0103 has no decimal point after digit 8. A trailing input dot
            // needs one blank cell to its right; an 8-cell integer is complete.
            if(entry_.find('.')==std::string::npos && cells<8) entry_+='.';
        }
        else {
            std::string magnitude=entry_[0]=='-'?entry_.substr(1):entry_;
            if(magnitude=="0") entry_=(entry_[0]=='-'?"-":"")+std::string(1,c);
            else {
                if(cells<8) entry_+=c;
            }
        }
        refresh(); return;
    }
    if(c=='B') {
        if(!entering_) { entry_="0"; entering_=true; repeat_operation_=0; }
        else if(!entry_.empty()) entry_.pop_back();
        if(entry_.empty()||entry_=="-") entry_="0";
        refresh(); return;
    }
    if(c=='+'||c=='-'||c=='*'||c=='/') {
        if(c=='-' && !entering_ && (pending_ || fresh_)) { entry_="-0"; entering_=true; fresh_=false; return; }
        if(pending_ && entering_) value_=Decimal::calculate(accumulator_,pending_,value_).for_display();
        accumulator_=value_; pending_=c; entering_=false; fresh_=false; repeat_operation_=0;
        return;
    }
    if(c=='=') {
        if(pending_) {
            repeat_operand_=entering_?value_:accumulator_; repeat_operation_=pending_;
            value_=Decimal::calculate(accumulator_,pending_,repeat_operand_).for_display(); pending_=0;
        } else if(repeat_operation_) value_=Decimal::calculate(value_,repeat_operation_,repeat_operand_).for_display();
        entering_=false; fresh_=false;
    }
}
}

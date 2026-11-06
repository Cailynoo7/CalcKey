#include "core.hpp"
#include <iostream>
int main() {
    std::string a,b;char op;
    while(std::cin>>a>>op>>b) {
        auto value=calckey::Decimal::parse(a);
        if(op!='@') value=calckey::Decimal::calculate(value,op,calckey::Decimal::parse(b));
        std::cout<<value.for_display().display_text()<<'\n';
    }
}

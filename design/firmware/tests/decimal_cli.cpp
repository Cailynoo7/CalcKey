#include "core.hpp"
#include <iostream>
int main() {
    std::string a,b; char op;
    while(std::cin>>a>>op>>b) std::cout<<calckey::Decimal::calculate(calckey::Decimal::parse(a),op,calckey::Decimal::parse(b)).text()<<'\n';
}

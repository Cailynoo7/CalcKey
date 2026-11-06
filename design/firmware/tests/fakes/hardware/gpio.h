#pragma once
#define GPIO_OUT true
void gpio_init(unsigned);
void gpio_put(unsigned,bool);
void gpio_set_dir(unsigned,bool);
void gpio_disable_pulls(unsigned);

# EDA-Keypad 参考资料摘记

来源：https://wiki.lceda.cn/zh-hans/course-projects/mcu32/32-rp2350-eda-keypad/eda-keypad-introduce.html
于2026-11-04在需求阶段读取，HTTP 200。

用户提供此项目作为功能与结构参考。原项目使用ColorEasyPico2 RP2350、SSD1306 0.91英寸屏、热插拔轴、EC11旋钮及WS2812。连接USB主机为HID小键盘，连接电源为计算器，介绍页未给内置电池方案。

本项目保留双模式用途；主控采用Raspberry Pi Pico 2，屏幕为Grove SSD1315，20键，独立计算时通过USB充电器供电，不安装电池。不能把参考外壳尺寸直接用于不同主控和显示模块。

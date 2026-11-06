# CalcKey Pico 2 固件 v0.2.0：GDM0103 八位LCD

已按现有Pico 2、20键二极管矩阵和GDM0103/HT1621B三线接线实现双模式。使用Pico SDK 2.2.0、TinyUSB 0.18.0及Arm GNU Toolchain 14.2.Rel1，版本固定于依赖锁定记录。本版本替换SSD1315 OLED显示实现；旧v0.1.0 ZIP保留作历史，不用于新LCD。

整机采用MATRIX A矩阵PCB：20键、4个10kΩ/0805上拉和J1～J10的10根引线；LCD五线独立接Pico，共15根。PCB替代逐键飞线，GPIO及二极管方向保持不变，固件版本仍为v0.2.0。制作使用矩阵PCB四页焊装图和逐项断电手册；旧手焊行列图及九页指南不用于本PCB焊盘定位。

用户要求先不烧录。本次只做源码、桌面测试、Pico 2交叉编译和交付文件检查，没有连接设备、烧录、通电或实机验收。编译和模拟测试通过不代表显示玻璃、矩阵、USB及供电已实测。

## GPIO和模块

接线以enclosure的wiring.json为准，check_wiring.py读取实际board_config.hpp常量，对照LCD五条线、20个开关/二极管和四个列上拉，检查引脚冲突及未使用的屏幕端子。

| 信号 | Pico GPIO / 物理针号 | 模块端子 |
| --- | --- | --- |
| LCD DATA | GP0 / 1 | P3 DATA |
| LCD 写时钟 | GP1 / 2 | P2 /WR |
| LCD 片选 | GP11 / 15 | P1 /CS |
| LCD电源 | 3V3 OUT / 36 | P5 VDD，仅3.3V版本 |
| LCD地 | GND / 38 | P4 VSS |
| 未使用 | 分别绝缘不接 | P6 /INT、P7 BL+、P8 BL-、P9 Ctrl |
| R0～R4 | GP2/4、GP3/5、GP4/6、GP5/7、GP6/9 | 二极管阴极色环 |
| C0～C3 | GP7/10、GP8/11、GP9/12、GP10/14 | 开关列线，各10k上拉到3V3 |
| USB | Pico原生Micro-B | 电脑或5V充电器，择一接入 |

初版不接背光。LCD没有I²C地址，不能沿用旧OLED线图和地址扫描。每键列→开关→1N4148阳极→阴极色环→行；扫描只把当前行拉低，其余高阻，内部上下拉均关闭。整矩阵目标2ms扫描，稳定5ms确认；主核栈4KiB，最坏栈峰值与真实扫描周期尚未实测。

## HT1621B驱动和段码

采用GPIO位操作写入。命令前缀100、8位命令MSB先发、末尾一位don't-care；RAM写前缀101、6位地址MSB先发，每个4位RAM数据按D0→D3顺序发送。/WR上升沿采样，名义低/高电平各5µs，约100kHz，CS建立/保持和事务间复位也留5µs。真实电平、波形及中断对脉冲宽度的影响仍需逻辑分析仪确认。

上电非阻塞等50ms，再按SYS DIS、LCD OFF、RC256K、1/3 bias/4 COM、WDT DIS、TIMER DIS、TONE OFF、IRQ DIS、NORMAL、SYS EN配置。完整写32个RAM地址后LCD ON。每次显示任务最多一条命令或四个RAM半字节，最长25个时钟、名义等待265µs；主循环只在距离下次扫描超过600µs时执行，持续服务TinyUSB。屏幕更新先完成当前帧，再接受新快照；连续输入不会饿死后半屏或第一次开屏。

前四位和后四位RAM排列不相同，按GDM0103手册PDF第8/12页明确映射A–G。小数点为CP1–CP4、CP7–CP9；中间冒号CP5/CP6关闭，未使用RAM清零。第8位右侧没有小数点：输入末尾的“12.”暂左移一格保留点，下一位输入后恢复右对齐；满8字符的整数不再接受小数点。输入“0.”、“-0.”保留输入状态，负零结果规范为0。

USB挂起时先LCD OFF、下一次任务SYS DIS，之后不重复写；恢复后等50ms重新配置、重绘。正常工作每5秒在空闲时重发配置及完整RAM，不先熄屏，以恢复LCD单独掉电造成的状态丢失。这套三线连接没有ACK或读回，软件不能确认屏幕是否存在或已经显示；模拟通过仅证明发送逻辑。禁止把“已发送”写成“屏幕在线”。缺屏时矩阵和USB仍可运行；改接线必须先断电，不把模拟重连测试当作热插拔授权。

## 模式和20键

| NumLock | ÷ | × | Backspace |
| --- | --- | --- | --- |
| 7 | 8 | 9 | − |
| 4 | 5 | 6 | + |
| 1 | 2 | 3 | Enter/= |
| Mode | 0 | . | AC |

上电为本地计算器；USB枚举配置完成才默认键盘模式，仅USB有电不算电脑连接。接电脑时Mode可切本地计算，本地计算不向电脑发计算键。模式切换、重新配置、USB传输失败和恢复先排队全释放报告，等实体键和去抖状态全部松开再接受输入。主机挂起保留模式，停止行驱动，不启用远程唤醒；如果移除主机只产生挂起事件，不通过超时猜测充电器，重新供电后重新判别。

切换时短暂显示CALC或PC（800ms）；计算数值变化立即结束提示，随后计算器显示数字。键盘模式常态显示PC 1或PC 0，代表主机NumLock报告开/关，未收到报告前按0显示。段码屏不常驻完整运算符、USB/POWER文字或历史记录。NumLock是否返回与小数键实际字符按操作系统/应用实测。

标准Boot Keyboard、数字小键盘usage、6键无冲；超过6个主机键发送ErrorRollOver。Mode与AC不映射主机键，AC在两模式均只清本地计算器。HID FIFO保留USB忙时短按顺序，溢出全释放并等待抬键，避免卡键。计算器数字不自动重复；Backspace按住500ms后每80ms重复，键盘长按由主机重复。

## 八字符计算规则

使用十进制系数/指数及12位内部算术保护精度，再把每一步结果量化到8个实际字符位。显示及下一步运算使用同一个量化结果，不保留隐藏的显示后小数。整数、前导零、小数中的零和负号都占字符，小数点不占字符。非负最多8位数字，负数最多7位数字；不采用科学计数法、不截断高位或符号。

每步按可用小数位四舍五入，恰好一半远离零。例如1÷6=0.1666667，接着×6=1.0000002；0.0000001÷2=0.0000001，÷3=0；负数最小一格为0.000001。舍入成零时取消负号。超过整数可显示范围或舍入进位越界均Err，例如99999999+1、−9999999−1；除零也为Err。可用AC或输入新数字/小数点恢复。输入超出8字符的额外数字忽略，Backspace仍可修正。

逐步计算，无表达式优先级：2+3×4=20。支持正负数、小数、退格、AC、连续操作符替换、重复等号和第二操作数负号（如2×−3=−6）。0.1+0.2=0.3；结果后新数字重新输入，操作符续算。

## 构建和交付

项目根目录执行：

```sh
python3 design/firmware/bootstrap.py
python3 design/firmware/build.py
```

工具已在项目缓存时无需重新bootstrap。bootstrap下载固定版本并检查锁定SHA256，只写项目工具缓存，不安装系统软件；自动下载针对macOS arm64。其他环境设置PICO_SDK_PATH、PICO_TINYUSB_PATH、PICO_TOOLCHAIN_PATH、CALCKEY_PICOTOOL_DIR，必要时CALCKEY_CMAKE、CALCKEY_NINJA、CXX_HOST。桌面测试需要Clang的AddressSanitizer/UndefinedBehaviorSanitizer。

构建依次检查接线、计算器/模式/去抖、独立GPIO波形解码和物理段码、2500组内部算术Python decimal对照、3023组8位符号/舍入/溢出对照，再交叉编译Pico 2。picotool只读取生成的UF2文件，确认RP2350 ARM Secure、pico2和版本0.2.0；另外检查所有UF2块、地址、family和RP2350-E10忽略块。不执行load、reboot或任何写设备命令。

当前交付为release/v0.2.0中的UF2、ELF、BIN、许可与verification.json，以及产品目录的calckey-firmware-v0.2.0.zip（含源码、测试、锁定版本、接线、需求和LCD说明）。验证记录包含命令输出、测试数量、日期、源码/接线/数据表SHA256和交付件哈希，flashed和hardware_tested均false。旧根release中的v0.1.0二进制及旧ZIP仅供历史查阅，不混入新包。

## 后续实机验收（本次不执行）

先核对当前矩阵PCB的J1～J10、LCD五线及PCB版断电检查。待用户另行要求烧录时才进行设备操作。验收表仍全部待测，应包括：电脑HID/NumLock/Mode、本机计算与PC不收键、充电器上电CALC、12345678/88888888及7个小数点位置、末尾点、负数、Err/AC、挂起/恢复、反复拔插和连续使用。真实显示顺序、视角/对比度、背光、电流、USB兼容性、机械配合和耐久均未实测。

## 证据与许可

- GDM0103厂商署名手册镜像：https://www.radiomag.com.de/datasheets/gdm0103_specification.pdf ，PDF第8页引脚/RAM、第9–11页协议、第12页物理数字/小数点/冒号分布。
- Holtek HT1621/1621G Rev3.40（含HT1621B）：https://www.holtek.com/webapi/116711/HT1621_21Gv340.pdf ，PDF第8页3V时序、第16–17页命令；本地保留原PDF及哈希。
- Pico 2：https://pip.raspberrypi.com/documents/RP-008299-DS ，第5页GPIO。
- 固定SDK：https://github.com/raspberrypi/pico-sdk/tree/2.2.0 ，TinyUSB：https://github.com/hathach/tinyusb/tree/0.18.0 。本次沿用现有构建/API，没有升级依赖。

VID 0xCAFE/PID 0x2350仅为样机测试标识，未声明商业分配。SDK BSD-3-Clause、TinyUSB MIT许可随包；项目自身尚未设置对外发布许可证。本次只构建和打包，不执行设备写入。

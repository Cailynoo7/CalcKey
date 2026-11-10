# CalcKey Type-C主控替代选型

2026-11-10。用户允许在现有平台索引之外查找市售主控板，优先减少对当前Pico 2方案的改动。本报告保留候选比较；采用16MB无排针版的当前数字装配与编译验证另记，不代表实物验收。

用户采用 **Waveshare RP2350-Plus-16MB，16MB Flash、不焊排针版，SKU 29761，1块**。原先4MB推荐被用户选择的16MB型号替代；不购买带排针的-M版本。原厂商品与资料可分别从 https://www.waveshare.net/shop/RP2350-Plus-16MB.htm 和 https://www.waveshare.net/wiki/RP2350-Plus 查找。此板不在项目平台索引中，不虚构索引ID。依据是RP2350A、Pico兼容40脚布局、与原板相同的4MB容量、原生USB Type-C及现有SDK自带板级配置，且已取得原厂机械图、原理图和STEP。

## 比较结论

| 候选 | 与当前设计关系 | 结论 |
|---|---|---|
| Waveshare RP2350-Plus 4MB，无排针 | 51×21mm板框、17.78mm排间距、2.54mm脚距；12路在用GPIO及3V3/GND脚对应一致；SDK 2.2.0已有专用配置 | 主推荐，电气与固件移植路径最明确 |
| WeAct Studio RP2350A_V20 4MB，无排针 | 原厂图为51×21mm、17.78mm排间距；Pico兼容脚位、USB-C，已下载原厂STEP | 次选；没有原板安装孔，当前SDK无该A_V20专用配置。不能误用RP2350B Core配置 |
| Pimoroni Pico Plus 2，PIM724 | PCB图为51×21mm，厂家整板含接插件约53×21×9mm；RP2350B、16MB Flash、8MB PSRAM及更多接插件 | 可用候选，但附加资源不服务本机需求，安装高度与配置改动更多 |
| Waveshare RP2350-USB-C | 名称相近，但为15路GPIO、额外PIO USB的不同小板布局 | 排除，不能当Pico 40脚兼容板 |

WeAct资料：https://github.com/WeActStudio/WeActStudio.RP2350ACoreBoard/tree/main/RP2350A_V20/HDK 。Pimoroni资料：https://shop.pimoroni.com/products/pimoroni-pico-plus-2 。被排除的同名近似板：https://docs.waveshare.com/RP2350-USB-C 。现货与价格未承诺，不引用第三方评测充当机械依据。

## 可以沿用的接口

根据微雪原厂引脚图及原理图第1页逐项核对：

| 用途 | GPIO | 物理脚号 |
|---|---|---|
| LCD DATA、WR、CS | GP0、GP1、GP11 | 1、2、15 |
| 矩阵R0～R4 | GP2、GP3、GP4、GP5、GP6 | 4、5、6、7、9 |
| 矩阵C0～C3 | GP7、GP8、GP9、GP10 | 10、11、12、14 |
| LCD和上拉电源 | 3V3 OUT | 36 |
| LCD地 | GND | 38 |

因此，按原GPIO关系迁移时，没有发现必须更改矩阵PCB网络的理由；这不等于换板装配与整机电气测试已经通过。原理图显示Type-C两组D+/D−合并后接原生USB控制器，CC1与CC2各有5.1kΩ下拉，具备USB设备供电连接的电路条件；A-C、C-C数据线及双面插入仍须实机验收。不需要新增USB转接小板。

## 必须改的地方

1. **固定结构**：微雪与WeAct厂家机械图均没有原版Pico的四个安装孔。现有底盖用两颗M2固定Pico，不能原封不动套用；后续根据STEP设计边缘固定或独立压片，并避让元件和焊点。不得在新板上自行钻孔。
2. **接口开口**：微雪图上USB-C壳宽8.95mm，前伸板边1.37mm，6.17mm标的是插座右缘到板右边，不能误读成插座中心偏移。必须按STEP检查旋转安装后的口位、插头外壳和USB侧支撑。旧Micro-B开口不能仅凭宽度宣称兼容。
3. **内部空间**：微雪板有电池座和充放电电路，本产品不接电池；电池座仍占空间，需检查底盖、矩阵板和线束桥间隙。不能把51×21mm板框当成完整器件包络。
4. **固件配置**：项目已锁定的Pico SDK 2.2.0自带 `waveshare_rp2350_plus_16mb`。现有CMake和构建脚本硬性限定 `pico2`，需要修改这些板级限制、版本标识和检查，再重新编译与测试。SDK默认I²C脚变化不影响现有三线GPIO驱动的LCD，但旧UF2没有替代板验证记录，不能直接称为兼容交付。
5. **交付同步**：实施换板时再更新正式BOM、接线、约束、采购、外壳和制作包。本次仅搜索选型，没有修改CAD、矩阵PCB、接线或固件，也没有下单、打印、上电或烧录。

## 证据与可追溯性

原厂原理图、尺寸图和引脚图已做视觉核读。微雪与WeAct原厂STEP均已下载，并检查STEP文件首尾标记；尚未导入整机做几何检查。微雪页面称Flash为片上容量，原理图实际为外置W25Q32JVSSIQ，报告按板载外部4MB Flash记录。

逐份来源URL、字节数和SHA256，以及GPIO对应和后续任务，保存在同名结构化JSON中。微雪英文站及GitHub API有403限制，分别使用微雪中文原站、文件站和WeAct原厂GitHub原始文件取得资料；没有从失败页面补猜尺寸。

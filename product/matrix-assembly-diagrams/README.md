# MATRIX A / RP2350-Plus-16MB / GDM0103焊装图

四页A3 PDF及同名SVG/PNG对应当前矩阵PCB发布和Type-C主控，不是1:1加工模板。主控为无排针SKU 29761、固件v0.3.0；Pico兼容物理脚号沿用，板形和Type-C口按微雪资料理解。

1. 01-component-orientation：矩阵正反面、20轴、二极管黑环和4只0805上拉。
2. 02-j1-j10-to-controller：J1～J10到主控的GPIO和物理脚号。主控元件面朝你、Type-C朝上；官方附图为背面，左右相反，按脚号核对。
3. 03-lcd-orientation-and-wiring：GDM0103正反面与五线；P6～P9各自绝缘、不接外部线。
4. 04-details-and-unpowered-checks：器件方向放大与断电测量。

矩阵10线、LCD5线，各默认150mm；J10与LCD P5接3V3 OUT/36，LCD P4接GND/38。矩阵没有GND端子，不接VBUS或5V。主控板载电池座不接。示意主控只用于读脚号，不画全实际元件，真实针序另附厂家引脚图。

逐步操作见guided-soldering.md、Type-C主控装配说明及整机154项空白表。59项电气记录仍待测；接入芯片后的信号不一律要求OL。插拔机械检查也须让USB线另一端悬空，不上电或烧录。旧to-pico图片不纳入当前完整包。

右键Product → Show in Finder查看PDF、SVG、PNG及CSV。生成依据和哈希见source-checks.json；图纸不代替实物测量。

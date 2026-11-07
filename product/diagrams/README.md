> 历史资料：手焊行列版接线图，不是当前MATRIX A矩阵PCB的操作依据。当前请用product/matrix-assembly-diagrams中的四页焊装图、guided-soldering操作手册与59项待测记录；不要按本目录重新并行列或采购轴向上拉电阻。

# CalcKey GDM0103 LCD接线焊接图（LCD-B / 固件v0.2.0）

交付四页A3横向矢量PDF、4张可编辑SVG、20键映射CSV和9端子LCD对照CSV。本版替换旧OLED图，适用于现有Pico 2、GDM0103/HT1621B的3.3V版本和20键矩阵，不改变硬件网络、固件或CAD。全程断电，不烧录。

1. 第1页：按键正面，20键、逐键1N4148和四个10k上拉。
2. 第2页：屏幕端向上的底面焊接视图，左右已镜像；开关电触点C/A是项目分配，不是实际机械脚位。
3. 第3页：Pico 2元件面/USB向上、14个已用物理针脚、LCD五线和四个上拉。
4. 第4页：GDM0103显示面与背面端子镜像、五根导线逐一对照及低位焊接说明。LCD P1–P9与Pico物理P1–P40分别标注，不能混用。

LCD：P1 /CS→GP11/物理15；P2 /WR→GP1/物理2；P3 DATA→GP0/物理1；P4 VSS→GND/物理38；P5 VDD→3V3(OUT)/物理36。P6 /INT、P7 BL+、P8 BL-、P9 Ctrl分别绝缘，不接外部线。三线写入，不是I²C；无Grove座改装、无四芯OLED线、无背光连线。NC不表示模块内部所有端子间都必须测为OL。

矩阵：列C→开关→二极管无环A→黑环K→行R。每列一只10k上拉到3V3；行不是GND。无实心圆点的行列交叉不连接，保持绝缘。Pico上拉电源端与LCD VDD共用3V3；不接VBUS、VSYS。线色只用于图示分类，实际靠端子标签核对。

LCD不装直立排针，P1–P5低位直焊；板背焊点/首段软线突出≤1.5mm，朝内折。矩阵九根主线与LCD五线各留约150mm维护余量。四处PCB边缘托架用0.15mm绝缘胶片，实物先确认空白承托带；先焊线检查，后粘PCB，不挤玻璃。无悬空焊点靠拉线承力，底盖完全分离仍需断开焊线。

配合更新后的九页A4断电焊接指南和五张空白实测表。散件/独立矩阵/加上拉/连接模块后的测量条件不同；不能在接Pico/LCD后要求列间严格20k或所有网络OL。所有实物项目仍待测，本图不是PCB或钻孔模板。

依据：Pico 2官方数据表PDF第5页图2（https://pip.raspberrypi.com/documents/RP-008299-DS）；厂商署名GDM0103手册PDF第7页外形/端子朝向、第8页针表（https://www.radiomag.com.de/datasheets/gdm0103_specification.pdf）；Vishay 1N4148 PDF第1页黑环K（https://www.vishay.com/docs/81857/1n4148.pdf）。生成时核对现有wiring.json和真实board_config.hpp的矩阵、LCD DATA/WR/CS常量。

重新生成：reportlab==4.4.3，CALCKEY_DIAGRAM_FONT可选中文TrueType字体；默认macOS Arial Unicode。脚本只生成文档，不写接线、器件清单或固件。

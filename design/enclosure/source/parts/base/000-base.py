
from screwjoint import make_screw_joint_v1, BossSpecV1
case_w=param("case_width",89.0)
case_d=param("case_depth",130.0)
base_h=param("base_height",18.0)
wall=param("wall_thickness",2.4)
floor=param("floor_thickness",2.4)
corner=param("corner_radius",6.0)
top_t=param("top_panel_thickness",3.0)
grid_y=param("key_grid_top_y",24.6)
pico_x=param("pico_x",16.4)
pico_y=param("pico_y",-10.0)
pico_z=param("pico_pcb_z",5.3)
usb_w=param("usb_cutout_width",13.0)
usb_h=param("usb_cutout_height",9.0)
usb_z=param("usb_cutout_z",7.3)
oled_y=param("display_y",49.0)
lcd_z=param("lcd_pcb_bottom",7.4)
lcd_w=param("lcd_board_width",78.0)
lcd_d=param("lcd_board_depth",26.0)
lcd_t=param("lcd_board_thickness",1.6)
lcd_max_t=param("lcd_module_max_thickness",10.0)
lcd_glue=param("lcd_mount_adhesive",0.15)
lcd_seat_w=param("lcd_seat_width",2.4)
lcd_seat_d=param("lcd_seat_depth",4.0)
lcd_fence_t=param("lcd_fence_thickness",2.0)
lcd_gap=param("lcd_edge_clearance",0.3)
lcd_seat_offset_y=param("lcd_seat_offset_y",8.0)
lip_depth=param("bottom_alignment_depth",2.0)
lip_gap=param("bottom_alignment_clearance",0.3)
lip_wall=param("bottom_alignment_wall",1.4)
tape_bridge_width=param("tape_bridge_width",16.0)
tape_slot_width=param("tape_slot_width",10.6)
tape_slot_height=param("tape_slot_height",2.0)
tape_bridge_roof=param("tape_bridge_roof",1.6)
tape_bridge_wall=param("tape_bridge_wall",2.0)
tape_bridge_round=param("tape_bridge_round",0.4)
matrix_keeper_y=param("matrix_keeper_y",-29.0)
lcd_keeper_y=param("lcd_keeper_y",23.0)
loop_keeper_x=param("loop_keeper_x",-26.0)
loop_keeper_y=param("loop_keeper_y",2.0)
h=part("rear_foot_left")
oled_z=lcd_z # compatibility name; the current module is GDM0103
PITCH=19.05 # exact CHERRY MX2A-L1NN data sheet
PICO_SEAT_BOTTOM=-0.05 # measured vendor STEP mounting pad underside
PICO_THICKNESS=0.96-PICO_SEAT_BOTTOM
key_xy=[((c-1.5)*PITCH,grid_y-r*PITCH) for r in range(5) for c in range(4)]
body_screw_xy=[(x,y) for x in (-case_w/2+3.8,case_w/2-3.8)
               for y in (grid_y-PITCH/2,grid_y-3.5*PITCH)]
pico_holes=[(pico_x-23.5,pico_y+y) for y in (-5.7,5.7)]
def rr(w,d,h,r):
    return extrude(RectangleRounded(w,d,r),h)
body=rr(case_w,case_d,floor,corner)
roof_blank=Pos(0,0,base_h)*rr(case_w,case_d,top_t,corner)
hood_bosses=[];hood_cuts=[];hardware=[];joint_records=[]
# These columns anchor to the actual unperforated roof lands outside the key grid.
# Explicit roof host avoids treating a nearby sidewall as material on the joint axis.
for i,(x,y) in enumerate(body_screw_xy):
    j=make_screw_joint_v1(size="M3",at=Location((x,y,0),(180,0,0)),
        through=[(body,floor)],engage_depth=5.0,into=roof_blank,
        head="button",material="PLA",boss=BossSpecV1(root_blend_mm=0),
        label=f"bottom:{i}")
    body=body-j.through_cuts
    hood_bosses.append(j.bosses);hood_cuts.append(j.engage_cuts)
    hardware.append(j.hardware)
    joint_records.append((f"bottom:{i}",j.screw_length_mm,j.boss_length_mm,j.bom))
for i,(x,y) in enumerate(pico_holes):
    board=Pos(pico_x,pico_y,pico_z+PICO_SEAT_BOTTOM)*Box(51,21,PICO_THICKNESS,align=(Align.CENTER,Align.CENTER,Align.MIN))
    j=make_screw_joint_v1(size="M2",at=Location((x,y,pico_z+0.96)),
        through=[(board,PICO_THICKNESS)],engage_depth=2.5,into=body,
        head="socket_cap",material="PLA",label=f"pico:{i}")
    body=body+j.bosses-j.engage_cuts
    hardware.append(j.hardware)
    joint_records.append((f"pico:{i}",j.screw_length_mm,j.boss_length_mm,j.bom))
for yy in (-8.3,8.3):
    body+=Pos(pico_x+23,pico_y+yy,floor-0.1)*Box(3.8,3.6,pico_z+PICO_SEAT_BOTTOM-floor+0.1,align=(Align.CENTER,Align.CENTER,Align.MIN))
# GDM0103 edge seats: do not guess the incompletely dimensioned mounting holes.
# Keep all glass/LED parts within the conservative 78 x 26 x 10 mm envelope.
lcd_seat_z=lcd_z-lcd_glue
lcd_seat_x=lcd_w/2-lcd_seat_w/2+0.4
lcd_fence_h=lcd_z+lcd_t+0.3
for sx in (-1,1):
    for sy in (-1,1):
        yy=oled_y+sy*lcd_seat_offset_y
        body+=Pos(sx*lcd_seat_x,yy,floor-0.1)*Box(
            lcd_seat_w,lcd_seat_d,lcd_seat_z-floor+0.1,align=(Align.CENTER,Align.CENTER,Align.MIN))
        body+=Pos(sx*(lcd_w/2+lcd_gap+lcd_fence_t/2),yy,floor-0.1)*Box(
            lcd_fence_t,lcd_seat_d+2,lcd_fence_h-floor+0.1,align=(Align.CENTER,Align.CENTER,Align.MIN))
# Two front stops stand clear of the first-row 16.4 mm switch/wiring keepouts.
for xx in (-30,30):
    body+=Pos(xx,oled_y-lcd_d/2-lcd_gap-lcd_fence_t/2,floor-0.1)*Box(
        4,lcd_fence_t,lcd_fence_h-floor+0.1,align=(Align.CENTER,Align.CENTER,Align.MIN))
assert lcd_z+lcd_max_t < base_h
ow=case_w-2*wall-2*lip_gap
od=case_d-2*wall-2*lip_gap
lip=Pos(0,0,floor-0.1)*rr(ow,od,lip_depth+0.1,corner-wall-lip_gap)
lip-=Pos(0,0,floor-0.2)*rr(ow-2*lip_wall,od-2*lip_wall,lip_depth+0.4,corner-wall-lip_gap-lip_wall)
for x,y in body_screw_xy:
    lip-=Pos(x,y,floor-0.3)*Cylinder(4.1,lip_depth+0.6,align=(Align.CENTER,Align.CENTER,Align.MIN))
lip-=Pos(case_w/2,pico_y,floor-0.3)*Box(12,usb_w+1,lip_depth+0.6,align=(Align.CENTER,Align.CENTER,Align.MIN))
body+=lip
for xx in (-h.hinge_x,h.hinge_x):
    for sgn in (-1,1):
        ex=xx+sgn*(h.width/2+h.side_gap+h.ear_t/2)
        ear=Rot(0,90,0)*Cylinder(h.ear_r,h.ear_t)
        ear+=Pos(0,0,(-h.hinge_z+0.1)/2)*Box(h.ear_t,2*h.ear_r,-h.hinge_z+0.1)
        ear-=Rot(0,90,0)*Cylinder(h.hole_r,h.ear_t+2)
        body+=Pos(ex,h.hinge_y,h.hinge_z)*ear
    body+=Pos(xx,h.hinge_y,h.hinge_z)*h.make_stop()
    low_stop_z=h.thickness/2-0.1
    body+=Pos(xx,h.hinge_y-h.length/2-1.25,h.hinge_z+low_stop_z)*Box(h.width,2.0,-h.hinge_z-low_stop_z+0.1,align=(Align.CENTER,Align.CENTER,Align.MIN))
# Integral tape bridges: 10 mm polyimide tape passes through the rounded tunnel.
# They clamp insulation only; no purchased clamp, screw, PCB hole or flexible snap.
tape_bridge_depth=tape_slot_width+2*tape_bridge_wall
tape_bridge_height=tape_slot_height+tape_bridge_roof
bridge_blank=Pos(0,0,-0.1)*Box(tape_bridge_width,tape_bridge_depth,tape_bridge_height+0.1,
    align=(Align.CENTER,Align.CENTER,Align.MIN))
bridge_top_edges=[e for e in bridge_blank.edges() if
    abs(e.bounding_box().min.Z-tape_bridge_height)<1e-6 and
    abs(e.bounding_box().max.Z-tape_bridge_height)<1e-6]
bridge_blank=fillet(bridge_top_edges,tape_bridge_round)
bridge_tunnel=Pos(-tape_bridge_width/2-1,0,tape_slot_height/2)*extrude(
    Plane.YZ*RectangleRounded(tape_slot_width,tape_slot_height,tape_bridge_round),
    tape_bridge_width+2)
tape_bridge=bridge_blank-bridge_tunnel
base_keeper_xy=[(0,matrix_keeper_y),(0,lcd_keeper_y),(loop_keeper_x,loop_keeper_y)]
for xx,yy in base_keeper_xy:
    body+=Pos(xx,yy,floor)*tape_bridge
connection_inventory={r[0]:"printed-screw-joint-v1" for r in joint_records}
connection_inventory.update({"bottom_alignment":"free: clearance tongue",
    "lens_to_top":"free: PSA perimeter","switch_to_plate":"free: MX clip lands",
    "pico_usb_support":"free: passive edge rests",
    "lcd_retention":"free: PCB edge seats, 0.15 mm insulating PSA, side and front stops",
    "lcd_wiring":"free: low-profile direct solder, no vertical headers"})
connection_inventory.update({"rear_left_hinge":"free: printed pin clevis with 110 degree hard stop",
    "rear_right_hinge":"free: printed pin clevis with 110 degree hard stop",
    "left_pin_retention":"free: bonded blind cap on axle only",
    "right_pin_retention":"free: bonded blind cap on axle only"})
connection_inventory.update({"harness_retention":"free: three integral rounded tape bridges; insulation only"})
assert len(joint_records)==6 and len(connection_inventory)==17
assert floor>=2 and wall>=2 and pico_z+PICO_SEAT_BOTTOM>floor
assert body.is_valid and len(body.solids())==1
for record in joint_records: print(record)
print("compact envelope",case_w,case_d,base_h+top_t,"GDM0103 PCB bottom",lcd_z,"Pico bottom",pico_z)
body.color=srgb("#273548")
publish("base",body,"Bottom service cover",material="pla")

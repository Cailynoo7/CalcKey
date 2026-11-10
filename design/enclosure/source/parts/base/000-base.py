
from screwjoint import make_screw_joint_v1, BossSpecV1
from portcut import port_cut, port_outline, PortSpec
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
PICO_SEAT_BOTTOM=-0.41148 # Waveshare shared STEP: PCB top z=0
PICO_THICKNESS=0.41148 # STEP representation, physical thickness remains an assembly check
key_xy=[((c-1.5)*PITCH,grid_y-r*PITCH) for r in range(5) for c in range(4)]
body_screw_xy=[(x,y) for x in (-case_w/2+3.8,case_w/2-3.8)
               for y in (grid_y-PITCH/2,grid_y-3.5*PITCH)]
pico_holes=[(pico_x-23.5,pico_y+y) for y in (-5.7,5.7)]
def rr(w,d,h,r):
    return extrude(RectangleRounded(w,d,r),h)
body=rr(case_w,case_d,floor,corner)
roof_blank=Pos(0,0,base_h)*rr(case_w,case_d,top_t,corner)
hood_bosses=[];hood_cuts=[];hardware=[];joint_records=[]
# Explicit surface seats retain the legacy clearance-only holes and proud heads.
# These columns anchor to the actual unperforated roof lands outside the key grid.
# Explicit roof host avoids treating a nearby sidewall as material on the joint axis.
for i,(x,y) in enumerate(body_screw_xy):
    j=make_screw_joint_v1(size="M3",at=Location((x,y,0),(180,0,0)),
        through=[(body,floor)],engage_depth=5.0,into=roof_blank,
        seat="surface",head="button",material="PLA",boss=BossSpecV1(root_blend_mm=0),
        label=f"bottom:{i}")
    body=body-j.through_cuts
    hood_bosses.append(j.bosses);hood_cuts.append(j.engage_cuts)
    hardware.append(j.hardware)
    joint_records.append((f"bottom:{i}",j.screw_length_mm,j.boss_length_mm,j.bom))
# No holes in this board: four edge seats, two removable insulated pressure bridges.
clamp_width=param("controller_clamp_width",6.0)
clamp_thickness=param("controller_clamp_thickness",3.0)
clamp_roof_z=param("controller_clamp_roof_z",9.2)
clamp_offset_a=param("controller_clamp_offset_a",-4.4)
clamp_offset_b=param("controller_clamp_offset_b",13.6)
clamp_screw_offset_y=param("controller_clamp_screw_offset_y",16.0)
controller_pad=param("controller_insulation_thickness",0.15)
controller_edge_land=param("controller_edge_land",1.4)
controller_stop_gap=param("controller_edge_stop_gap",0.30)
clamp_x=[pico_x+clamp_offset_a,pico_x+clamp_offset_b]
clamp_shapes=[]
clamp_joint_records=[]
seat_z=pico_z+PICO_SEAT_BOTTOM-controller_pad
contact_bottom=pico_z+controller_pad
for k,xx in enumerate(clamp_x):
    for yy in (pico_y-9.8,pico_y+9.8):
        body+=Pos(xx,yy,floor-0.1)*Box(clamp_width,controller_edge_land,seat_z-floor+0.1,align=(Align.CENTER,Align.CENTER,Align.MIN))
        # Lateral locating fences stay outside the castellated PCB edge.
        sy=-1 if yy<pico_y else 1
        body+=Pos(xx,pico_y+sy*(10.5+controller_stop_gap+0.7),floor-0.1)*Box(clamp_width,1.4,pico_z-floor+0.1,align=(Align.CENTER,Align.CENTER,Align.MIN))
    blank=Pos(xx,pico_y,clamp_roof_z)*Box(clamp_width,2*clamp_screw_offset_y+6,clamp_thickness,align=(Align.CENTER,Align.CENTER,Align.MIN))
    for yy in (pico_y-9.8,pico_y+9.8):
        blank+=Pos(xx,yy,contact_bottom)*Box(clamp_width,controller_edge_land,clamp_roof_z-contact_bottom+0.1,align=(Align.CENTER,Align.CENTER,Align.MIN))
    for side in (-1,1):
        yy=pico_y+side*clamp_screw_offset_y
        j=make_screw_joint_v1(size="M2",at=Location((xx,yy,clamp_roof_z+clamp_thickness)),
            through=[(blank,clamp_thickness)],seat="counterbore",head="socket_cap",
            engage_depth=5.0,into=body,material="PLA",label=f"controller:{k}:{side}")
        blank=blank-j.through_cuts
        body=body+j.bosses-j.engage_cuts
        hardware.append(j.hardware)
        joint_records.append((f"controller:{k}:{side}",j.screw_length_mm,j.boss_length_mm,j.bom))
        clamp_joint_records.append((k,side,j.screw_length_mm,j.head_above_surface_mm))
    assert blank.is_valid and len(blank.solids())==1
    clamp_shapes.append(blank)
# Rear end stops take USB insertion load; housing wall limits forward board motion.
for yy in (pico_y-6,pico_y+6):
    body+=Pos(pico_x-25.5-controller_stop_gap-0.8,yy,floor-0.1)*Box(1.6,4.0,pico_z-floor+0.1,align=(Align.CENTER,Align.CENTER,Align.MIN))
usb_center_y=pico_y+10.5-10.4900469477
usb_body_center_z=pico_z+1.16952175415
# Front rim from Waveshare STEP Type_C1/front face: 8.94 x 3.16, R1.28.
# The whole component includes lower feet; do not centre the mouth on those.
usb_center_z=pico_z+1.669521495
usb_front_x=pico_x-25.5+52.3119298631
usb_recess=case_w/2-usb_front_x
usb_clearance=param("usb_c_extra_clearance",0.25)
usb_rim_depth=param("usb_c_front_rim_depth",0.7)
port_bezel_w=param("usb_service_tongue_width",14.5)
port_bezel_h=param("usb_service_tongue_height",11.2)
port_bezel_gap=param("usb_service_tongue_gap",0.25)
usb_cut=port_cut(PortSpec("rounded",8.94+2*usb_clearance,3.16+2*usb_clearance,1.28+usb_clearance),at=(case_w/2,usb_center_y,usb_center_z),facing="+X",depth=wall+1.5,clearance=0.0)
# Rear shield is larger: relieve inside but keep a profiled outer lip.
usb_inner_cut=port_cut(PortSpec("rounded",10.18,4.76,1.58),at=(case_w/2-usb_rim_depth,usb_center_y,usb_body_center_z),facing="+X",depth=wall+1.5,clearance=0.0)
usb_inner_clip=Pos(case_w/2-usb_rim_depth-(wall+2)/2,usb_center_y,usb_body_center_z)*Box(wall+2,port_bezel_w,port_bezel_h)
usb_inner_cut=usb_inner_cut & usb_inner_clip
port_service_bay=port_cut(PortSpec("rounded",port_bezel_w+2*port_bezel_gap,2*(port_bezel_h+port_bezel_gap),1.25),at=(case_w/2,usb_center_y,0),facing="+X",depth=wall+1.5)
port_tongue=Pos(case_w/2-wall,usb_center_y,port_bezel_h/2)*extrude(Plane.YZ*port_outline(PortSpec("rounded",port_bezel_w,port_bezel_h,1.0)),wall)
# Internal PCB-edge relief, not an external connector opening; outer slot stays capsule-shaped.
controller_wall_relief=Pos(case_w/2-wall-0.1,pico_y,pico_z+PICO_SEAT_BOTTOM/2)*Box(1.05,22.0,PICO_THICKNESS+0.5,align=(Align.MIN,Align.CENTER,Align.CENTER))
controller_wall_service_relief=Pos(case_w/2-wall-0.1,pico_y,floor-0.1)*Box(1.05,22.0,pico_z+0.25-floor+0.1,align=(Align.MIN,Align.CENTER,Align.MIN))
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
lip-=Pos(0,0,floor-0.2)*rr(ow-2*lip_wall,od-2*lip_wall,lip_depth+0.4,max(0.4,corner-wall-lip_gap-lip_wall))
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
    "pico_usb_support":"free: four insulated edge seats and two removable screw pressure bridges",
    "lcd_retention":"free: PCB edge seats, 0.15 mm insulating PSA, side and front stops",
    "lcd_wiring":"free: low-profile direct solder, no vertical headers"})
connection_inventory.update({"rear_left_hinge":"free: printed pin clevis with 110 degree hard stop",
    "rear_right_hinge":"free: printed pin clevis with 110 degree hard stop",
    "left_pin_retention":"free: bonded blind cap on axle only",
    "right_pin_retention":"free: bonded blind cap on axle only"})
connection_inventory.update({"harness_retention":"free: three integral rounded tape bridges; insulation only"})
assert len(joint_records)==8 and len(connection_inventory)==19
assert floor>=2 and wall>=2 and pico_z+PICO_SEAT_BOTTOM>floor
print("controller clamps",clamp_joint_records,"USB C centre",usb_center_y,usb_center_z,"recess",usb_recess)
assert body.is_valid and len(body.solids())==1
for record in joint_records: print(record)
print("compact envelope",case_w,case_d,base_h+top_t,"GDM0103 PCB bottom",lcd_z,"Pico bottom",pico_z)
body+=port_tongue
body-=usb_cut
body-=usb_inner_cut
body-=controller_wall_relief
assert body.is_valid and len(body.solids())==1
body.color=srgb("#C4E4DA")
publish("base",body,"Bottom service cover",material="pla")

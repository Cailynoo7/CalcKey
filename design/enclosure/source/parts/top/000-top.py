# cell: top
# cell: top

b=part("base")
key_hole=param("key_hole_size",14.2)
clip_pocket=param("key_clip_pocket",16.4)
clip_land=param("key_clip_land_thickness",1.5)
window_w=param("screen_window_width",32.0)
window_d=param("screen_window_depth",24.0)
lens_pocket_depth=param("lens_pocket_depth",1.35)
pocket_w=param("lens_pocket_width",36.0)
pocket_d=param("lens_pocket_depth_y",28.0)
bevel=param("outer_edge_bevel",0.4)
engrave=param("front_engrave_depth",0.35)
mark_h=param("front_mark_height",3.2)
mark_z=param("front_mark_z",10.8)
panel=b.roof_blank
outer=Pos(0,0,b.floor)*extrude(RectangleRounded(b.case_w,b.case_d,b.corner),b.base_h-b.floor+0.1)
inner=Pos(0,0,b.floor-0.1)*extrude(RectangleRounded(b.case_w-2*b.wall,b.case_d-2*b.wall,b.corner-b.wall),b.base_h-b.floor+0.3)
panel+=outer-inner
for boss in b.hood_bosses: panel+=boss
for cut in b.hood_cuts: panel-=cut
for x,y in b.key_xy:
    panel-=Pos(x,y,b.base_h-0.5)*Box(key_hole,key_hole,b.top_t+1,align=(Align.CENTER,Align.CENTER,Align.MIN))
    panel-=Pos(x,y,b.base_h-0.5)*Box(clip_pocket,clip_pocket,b.top_t-clip_land+0.5,align=(Align.CENTER,Align.CENTER,Align.MIN))
panel-=Pos(0,b.oled_y,b.base_h-1)*extrude(RectangleRounded(window_w,window_d,1),b.top_t+2)
panel-=Pos(0,b.oled_y,b.base_h-0.1)*extrude(RectangleRounded(pocket_w,pocket_d,1.2),lens_pocket_depth+0.1)
panel-=Pos(b.case_w/2,b.pico_y,b.floor-0.1)*Box(12,b.usb_w,b.usb_z+b.usb_h/2-b.floor+0.2,align=(Align.CENTER,Align.CENTER,Align.MIN))
assert b.wall-engrave>=2.0
outer_edges=[]
for edge in panel.edges():
    bb=edge.bounding_box()
    if abs(bb.min.Z-(b.base_h+b.top_t))<1e-6 and abs(bb.max.Z-(b.base_h+b.top_t))<1e-6:
        if max(abs(bb.min.X),abs(bb.max.X))>b.case_w/2-0.01 or max(abs(bb.min.Y),abs(bb.max.Y))>b.case_d/2-0.01:
            outer_edges.append(edge)
assert len(outer_edges)==8
panel=chamfer(outer_edges,length=bevel)
panel-=Pos(0,-b.case_d/2+engrave,mark_z)*extrude(Plane.XZ*Text("CALC",mark_h,font="Arial"),engrave+0.15)
for xx in (-34,-30,27,31):
    slash=Polygon((xx-0.4,mark_z-3),(xx+0.4,mark_z-3),(xx+2.8,mark_z+3),(xx+2.0,mark_z+3),align=None)
    panel-=Pos(0,-b.case_d/2+engrave,0)*extrude(Plane.XZ*slash,engrave+0.15)
assert panel.is_valid and len(panel.solids())==1
print("integral upper housing",b.case_w,b.case_d,"bottom opening at",b.floor)
print("window",window_w,window_d,"PCB columns now on bottom cover")
panel.color=srgb("#354151")
publish("top",panel,"Main key housing",material="pla")

# Same 20 nominal KS-9 locator ribs, now carried by the released PCB assembly.
fit("matrix_pcb","top",kind="compliant",budget_mm=0.16,reason="Released matrix assembly contains the 20 original KS-9 locator ribs; original per-switch depth 0.1374 mm, physical retention remains untested")

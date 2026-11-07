plate_w=param("plate_width",70.0)
plate_d=param("plate_depth",60.0)
plate_t=param("plate_thickness",3.0)
corner=param("outer_corner_radius",3.0)
pitch_x=param("station_pitch_x",23.0)
pitch_y=param("station_pitch_y",24.0)
hole_current=param("current_hole_width",14.2)
hole_step=param("hole_width_step",0.1)
pocket=param("clip_pocket_width",16.4)
land=param("current_clip_land",1.5)
land_step=param("clip_land_step",0.15)
label_size=param("label_font_size",4.2)
label_depth=param("label_engrave_depth",0.3)
# C copies current housing interface, other stations are experiment defaults.
stations=[
 ("A",-pitch_x,pitch_y/2,hole_current-2*hole_step,land),
 ("B",0,pitch_y/2,hole_current-hole_step,land),
 ("C",pitch_x,pitch_y/2,hole_current,land),
 ("D",-pitch_x,-pitch_y/2,hole_current+hole_step,land),
 ("E",0,-pitch_y/2,hole_current,land-land_step),
 ("F",pitch_x,-pitch_y/2,hole_current,land+land_step)]
assert plate_t>land+land_step>land-land_step>0
assert pitch_x-pocket>=2 and pitch_y-pocket>=2
assert plate_w/2-pitch_x-pocket/2>=2
assert plate_d/2-pitch_y/2-pocket/2>=2
body=extrude(RectangleRounded(plate_w,plate_d,corner),plate_t)
label_cuts=[]
for ident,x,y,hole,clip_land in stations:
    assert 0<hole<pocket and (pocket-hole)/2>=1.0
    body-=Pos(x,y,-0.1)*Box(hole,hole,plate_t+0.2,align=(Align.CENTER,Align.CENTER,Align.MIN))
    body-=Pos(x,y,-0.1)*Box(pocket,pocket,plate_t-clip_land+0.1,align=(Align.CENTER,Align.CENTER,Align.MIN))
    sign=1 if y>0 else -1
    for label,ly in [(ident+f"{hole:.1f}",sign*(pitch_y/2+11)),(f"T{clip_land:.2f}",sign*(pitch_y/2+15))]:
        text_shape=Pos(x,ly,plate_t-label_depth)*extrude(Text(label,label_size,font="Arial"),label_depth+0.1)
        bb=text_shape.bounding_box()
        assert bb.min.X>-plate_w/2 and bb.max.X<plate_w/2
        assert bb.min.Y>-plate_d/2 and bb.max.Y<plate_d/2
        label_cuts.append(text_shape)
for cut in label_cuts: body-=cut
assert body.is_valid and len(body.solids())==1
connection_inventory={ident:"free: actual switch spring clips on printed land" for ident,*_ in stations}
assert len(connection_inventory)==6
body.color=srgb("#2c8f9b")
publish("plate",body,"Six-hole switch fit coupon",material="pla")
print("coupon size",plate_w,plate_d,plate_t,"pocket",pocket)
print("stations",stations)
print("minimum XY ligament",min(pitch_x-pocket,pitch_y-pocket))

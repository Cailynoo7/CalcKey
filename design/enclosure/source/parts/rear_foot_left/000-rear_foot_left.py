
from math import radians,degrees,sin,cos,atan
width=param("rear_foot_width",10.0)
length=param("rear_foot_length",8.5)
thickness=param("rear_foot_thickness",3.6)
hub_r=param("hinge_hub_radius",2.6)
pin_d=param("hinge_pin_diameter",2.4)
pin_clearance=param("hinge_diameter_clearance",0.4)
hinge_x=param("hinge_x",31.5)
hinge_y=param("hinge_y",50.0)
hinge_z=param("hinge_z",-3.2)
deployment=param("deployment_angle",110.0)
high_tilt=param("keyboard_high_tilt",4.0)
low_depth=param("stowed_rear_depth",6.8)
front_contact=param("front_support_y",64.0)
front_pad_t=param("front_pad_thickness",2.0)
ear_t=param("hinge_ear_thickness",3.0)
ear_r=param("hinge_ear_radius",3.0)
side_gap=param("hinge_side_gap",0.25)
cam_half=param("stop_cam_half_width",0.8)
cam_reach=param("stop_cam_reach",3.8)
edge_break=param("foot_edge_break",0.2)
low_tilt=degrees(atan((low_depth-front_pad_t)/(hinge_y+front_contact)))
def pose_lift(a): return front_contact*sin(radians(a))+front_pad_t*cos(radians(a))
high_lift=pose_lift(high_tilt)
low_lift=pose_lift(low_tilt)
hole_r=(pin_d+pin_clearance)/2
assert hub_r-hole_r>=1.2 and side_gap>=0.2 and ear_t>=3
def make_foot(edge):
    f=Pos(0,-length/2+0.75,-0.1)*Box(width,length,thickness)
    f+=Rot(0,90,0)*Cylinder(hub_r,width)
    cam_top=-(hub_r-0.3)
    f+=Pos(0,-cam_half,(cam_top-cam_reach)/2)*Box(width,cam_half*2,cam_top+cam_reach)
    low_plane=-low_depth-hinge_z
    f-=Pos(0,0,low_plane)*Rot(-low_tilt,0,0)*Box(100,100,100,align=(Align.CENTER,Align.CENTER,Align.MAX))
    f=Rot(deployment,0,0)*f
    level=-(high_lift+hinge_y*sin(radians(high_tilt))+hinge_z*cos(radians(high_tilt)))/cos(radians(high_tilt))
    f-=Pos(0,0,level)*Rot(-high_tilt,0,0)*Box(100,100,100,align=(Align.CENTER,Align.CENTER,Align.MAX))
    f=Rot(-deployment,0,0)*f
    f-=Rot(0,90,0)*Cylinder(hole_r,width+2)
    # Preserve both sole faces and the stop face; only soften longitudinal end edges.
    edges=[e for e in f.edges() if abs(e.bounding_box().min.X-e.bounding_box().max.X)<1e-6 and abs(abs(e.center().X)-width/2)<1e-5 and e.geom_type==GeomType.LINE and e.length>4]
    f=chamfer(edges,length=edge)
    return f
def make_stop():
    ny=cos(radians(deployment));nz=sin(radians(deployment))
    ya=hub_r+0.3;yb=cam_reach+1
    line=lambda y:(-ny*y)/nz
    return Pos(-width/2,0,0)*extrude(Plane.YZ*Polygon((ya,line(ya)),(yb,line(yb)),(yb,-hinge_z+0.1),(ya,-hinge_z+0.1),align=None),width)
foot=make_foot(edge_break)
assert foot.is_valid and len(foot.solids())==1
foot.color=srgb("#1e8995")
publish("rear_foot_left",foot,"Left folding foot",material="petg")
print("low/high tilt",low_tilt,high_tilt,"deployment",deployment,"high lift",high_lift)

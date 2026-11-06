
left=part("hinge_axle_left")
head_t=param("right_axle_head_thickness",1.5)
axle=left.make_axle(head_t)
assert axle.is_valid and len(axle.solids())==1
axle.color=srgb("#354151")
publish("hinge_axle_right",axle,"Right hinge axle",material="petg")

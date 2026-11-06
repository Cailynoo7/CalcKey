
b=part("base")
lens_w=param("lens_width",29.6)
lens_d=param("lens_depth",21.6)
lens_t=param("lens_thickness",1.0)
lens_corner=param("lens_corner_radius",1.0)
window=extrude(RectangleRounded(lens_w,lens_d,lens_corner),lens_t)
window.color=srgb("#173746",0.65)
publish("screen_lens",window,"Acrylic display lens",material="acrylic")

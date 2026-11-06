# Exact manufacturer asset already bound by sw_01; rigid instance only.
orientation=param("sw_10_orientation_deg",0)
switch=Rot(0,0,orientation)*asset("design/enclosure/source/assets/29f4d60beb57a869d233939c629de23319458d225f0be6644fd86258533e3c9d.step")
publish("sw_10",switch,"KS9 red 10",role="reference")
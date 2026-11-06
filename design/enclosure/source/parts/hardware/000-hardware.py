
b=part("base")
z_offset=param("fastener_display_z_offset",0.0)
publish("screws",[Pos(0,0,z_offset)*s for s in b.hardware],"Assembly screws",material="stainless_steel",role="fastener")

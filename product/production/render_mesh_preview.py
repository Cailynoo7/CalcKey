"""Render the two feature-bearing delivered STLs without a GUI or slicer."""
from pathlib import Path
import struct
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.work/production'
OUT.mkdir(parents=True,exist_ok=True)
fig=plt.figure(figsize=(12,6),facecolor='#f3f5f7')
for i,(name,title) in enumerate([('key_10','5 | recessed locator'),('key_16','Enter / = | two-line legend')],1):
    data=(ROOT/'product/production/models'/f'{name}.stl').read_bytes()
    count=struct.unpack_from('<I',data,80)[0]
    dtype=np.dtype([('n','<f4',(3,)),('v','<f4',(3,3)),('a','<u2')])
    t=np.frombuffer(data,dtype=dtype,count=count,offset=84)['v'].astype(float).copy()
    t[:,:,1]*=-1;t[:,:,2]=7-t[:,:,2]
    normals=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
    normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
    visible=normals[:,2]>1e-7
    t=t[visible];normals=normals[visible]
    light=np.array([-.45,-.65,1.0]);light/=np.linalg.norm(light)
    shade=.45+.5*np.maximum(normals@light,0)-.18*np.clip((7-t[:,:,2].mean(axis=1))/.35,0,1)
    colors=np.column_stack([shade*.93,shade*.95,shade*.97,np.ones(len(shade))])
    ax=fig.add_subplot(1,2,i,projection='3d',facecolor='#f3f5f7')
    ax.add_collection3d(Poly3DCollection(t,facecolors=colors,edgecolor='none',linewidth=0,antialiased=False,zsort='average'))
    ax.set_proj_type('ortho')
    ax.set(xlim=(-10,10),ylim=(-10,10),zlim=(-.5,7.5))
    # Top projection keeps the painter renderer's depth order unambiguous;
    # an oblique view of long coplanar STL triangles can show false seams.
    ax.set_box_aspect((20,20,8));ax.view_init(elev=90,azim=-90)
    ax.set_axis_off();ax.set_title(title,pad=4,color='#203346',fontsize=15)
fig.subplots_adjust(left=0,right=1,bottom=0,top=.88,wspace=-.06)
fig.suptitle('CalcKey | Delivered STL geometry | no slicing / printing',fontsize=17,color='#203346')
fig.savefig(OUT/'keycap-mesh-preview.png',dpi=160,facecolor=fig.get_facecolor())
print('Rendered .work/production/keycap-mesh-preview.png')

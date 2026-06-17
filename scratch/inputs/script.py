import numpy as np
import plotly.graph_objects as go

Gm = 32.3
Ls = -15.0
LF = 0.0

psi_b = 1.0

psi = np.linspace(0, 40, 2001)

G = np.empty_like(psi)

# main beam region 0<psi<=psi_b
mb = (psi > 0) & (psi <= psi_b)
G[mb] = Gm - 3*(psi[mb]/psi_b)**2

# transition Y
Y = psi_b * np.sqrt(-Ls/3.0)

mid = (psi > psi_b) & (psi <= Y)
G[mid] = Gm - 3*(psi[mid]/psi_b)**2

mid2 = (psi > Y)
G[mid2] = Gm + Ls - 25*np.log10(psi[mid2]/Y)

Z = Y * 10**(0.04*(Gm + Ls - LF))
far = psi > Z
G[far] = LF

fig = go.Figure()
fig.add_trace(go.Scatter(x=psi, y=G, mode='lines', name='Pattern'))
fig.update_layout(title='ITU-R S.1528 pattern, Gm=32.3 dBi, Ls=-15 dB',
                  xaxis_title='Off-axis angle ψ (deg)',
                  yaxis_title='Gain G(ψ) (dBi)',
                  xaxis_range=[0,40])

import os
os.makedirs('output', exist_ok=True)
fig.write_image('output/ITU_S1528_Gm32p3_Ls-15.png')

'output/ITU_S1528_Gm32p3_Ls-15.png'
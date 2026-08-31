# VAJRA — the loop, closed

Gate difficulty held FROZEN at 0.026 for the whole run, so the attacker and the defender cannot co-drift into a meaningless number.

## Arms

| Arm | What is disabled | Cells occupied | Coverage | Solvent coverage |
|---|---|---|---|---|
| full | full hierarchical agent | 144/380 | 37.89% | 37.63% |
| random_tactic | random_tactic (Level 2 replaced by uniform random choice) | 144/380 | 37.89% | 37.89% |
| bandit_only | bandit_only (Level 2 disabled) | 144/380 | 37.89% | 37.63% |
| static | static (loop disabled) | 142/380 | 37.37% | 37.37% |

## LOOP-LIFT and the RL ablations

| Comparison | Verdict |
|---|---|
| LOOP-LIFT (full vs static, no loop) | NO MEASURED EFFECT (delta +0.0053 coverage, below the 0.01 single-seed resolution) |
| what the MDP level bought (full vs bandit-only) | NO MEASURED EFFECT (delta +0.0000 coverage, below the 0.01 single-seed resolution) |
| what credit assignment bought (full vs random tactic) | NO MEASURED EFFECT (delta +0.0000 coverage, below the 0.01 single-seed resolution) |
| time-to-evade: full vs static (probe budget) | -3.9 probes |
| time-to-evade: full vs bandit-only (probe budget) | +1.2 probes |

n=1. These are SINGLE RUNS ON ONE SEED. A single-seed delta is weak evidence and we label it rather than dressing it up. If `bandit_only` matches `full`, the MDP level bought nothing on this run and we report that.


archive coverage over the pre-declared feasible denominator. The design's LOOP-LIFT is also defined on withheld-family recall and venue-authored recall; those require the full `make eval` path and the venue slot respectively, and the venue slot is BLANK until an outsider fills it.


## Tick timings (displayed whatever they read)

| Tick | Wall clock | Proposals | Admitted | Cells |
|---|---|---|---|---|
| 1 | 0.12s | 3 | 3 | 3 |
| 2 | 0.04s | 3 | 1 | 4 |
| 3 | 0.06s | 3 | 0 | 4 |
| 4 | 0.03s | 3 | 3 | 6 |
| 5 | 0.04s | 3 | 3 | 9 |
| 6 | 0.06s | 3 | 1 | 10 |
| 7 | 0.04s | 3 | 2 | 12 |
| 8 | 0.05s | 3 | 2 | 14 |
| 9 | 0.06s | 3 | 0 | 14 |
| 10 | 0.05s | 3 | 3 | 17 |
| 11 | 0.06s | 3 | 1 | 18 |
| 12 | 0.04s | 3 | 3 | 21 |
| 13 | 0.05s | 3 | 1 | 22 |
| 14 | 0.05s | 3 | 2 | 23 |
| 15 | 0.04s | 3 | 2 | 25 |
| 16 | 0.05s | 3 | 2 | 26 |
| 17 | 0.05s | 3 | 1 | 27 |
| 18 | 0.04s | 3 | 2 | 29 |
| 19 | 0.06s | 3 | 0 | 29 |
| 20 | 0.05s | 3 | 1 | 30 |
| 21 | 0.05s | 3 | 1 | 30 |
| 22 | 0.04s | 3 | 3 | 32 |
| 23 | 0.03s | 3 | 3 | 35 |
| 24 | 0.06s | 3 | 0 | 35 |
| 25 | 0.05s | 3 | 0 | 35 |
| 26 | 0.04s | 3 | 3 | 38 |
| 27 | 0.04s | 3 | 1 | 39 |
| 28 | 0.04s | 3 | 1 | 40 |
| 29 | 0.04s | 3 | 1 | 40 |
| 30 | 0.04s | 3 | 1 | 41 |
| 31 | 0.03s | 3 | 2 | 43 |
| 32 | 0.04s | 3 | 2 | 45 |
| 33 | 0.06s | 3 | 1 | 46 |
| 34 | 0.06s | 3 | 1 | 47 |
| 35 | 0.04s | 3 | 0 | 47 |
| 36 | 0.06s | 3 | 1 | 48 |
| 37 | 0.03s | 3 | 1 | 49 |
| 38 | 0.05s | 3 | 1 | 50 |
| 39 | 0.05s | 3 | 0 | 50 |
| 40 | 0.05s | 3 | 2 | 51 |
| 41 | 0.05s | 3 | 0 | 51 |
| 42 | 0.04s | 3 | 1 | 52 |
| 43 | 0.03s | 3 | 2 | 54 |
| 44 | 0.04s | 3 | 1 | 55 |
| 45 | 0.05s | 3 | 2 | 56 |
| 46 | 0.05s | 3 | 0 | 56 |
| 47 | 0.03s | 3 | 1 | 57 |
| 48 | 0.04s | 3 | 1 | 57 |
| 49 | 0.06s | 3 | 1 | 58 |
| 50 | 0.06s | 3 | 2 | 59 |
| 51 | 0.05s | 3 | 1 | 60 |
| 52 | 0.04s | 3 | 1 | 61 |
| 53 | 0.03s | 3 | 3 | 63 |
| 54 | 0.04s | 3 | 2 | 65 |
| 55 | 0.05s | 3 | 1 | 65 |
| 56 | 0.04s | 3 | 3 | 67 |
| 57 | 0.06s | 3 | 1 | 68 |
| 58 | 0.05s | 3 | 0 | 68 |
| 59 | 0.06s | 3 | 1 | 69 |
| 60 | 0.05s | 3 | 2 | 71 |
| 61 | 0.05s | 3 | 3 | 74 |
| 62 | 0.04s | 3 | 1 | 75 |
| 63 | 0.04s | 3 | 2 | 76 |
| 64 | 0.06s | 3 | 0 | 76 |
| 65 | 0.07s | 3 | 0 | 76 |
| 66 | 0.06s | 3 | 0 | 76 |
| 67 | 0.04s | 3 | 2 | 78 |
| 68 | 0.06s | 3 | 1 | 79 |
| 69 | 0.05s | 3 | 3 | 82 |
| 70 | 0.04s | 3 | 2 | 83 |
| 71 | 0.03s | 3 | 2 | 84 |
| 72 | 0.05s | 3 | 1 | 84 |
| 73 | 0.07s | 3 | 0 | 84 |
| 74 | 0.06s | 3 | 0 | 84 |
| 75 | 0.06s | 3 | 2 | 86 |
| 76 | 0.06s | 3 | 2 | 88 |
| 77 | 0.04s | 3 | 3 | 91 |
| 78 | 0.06s | 3 | 0 | 91 |
| 79 | 0.06s | 3 | 1 | 91 |
| 80 | 0.05s | 3 | 1 | 92 |
| 81 | 0.07s | 3 | 2 | 92 |
| 82 | 0.05s | 3 | 1 | 93 |
| 83 | 0.04s | 3 | 3 | 94 |
| 84 | 0.06s | 3 | 1 | 95 |
| 85 | 0.06s | 3 | 1 | 95 |
| 86 | 0.05s | 3 | 2 | 97 |
| 87 | 0.07s | 3 | 1 | 97 |
| 88 | 0.06s | 3 | 0 | 97 |
| 89 | 0.04s | 3 | 1 | 98 |
| 90 | 0.07s | 3 | 1 | 99 |
| 91 | 0.07s | 3 | 0 | 99 |
| 92 | 0.06s | 3 | 2 | 101 |
| 93 | 0.06s | 3 | 1 | 101 |
| 94 | 0.06s | 3 | 0 | 101 |
| 95 | 0.05s | 3 | 2 | 103 |
| 96 | 0.06s | 3 | 2 | 105 |
| 97 | 0.06s | 3 | 1 | 106 |
| 98 | 0.06s | 3 | 1 | 106 |
| 99 | 0.08s | 3 | 1 | 106 |
| 100 | 0.05s | 3 | 3 | 107 |
| 101 | 0.05s | 3 | 1 | 108 |
| 102 | 0.05s | 3 | 1 | 108 |
| 103 | 0.07s | 3 | 2 | 109 |
| 104 | 0.06s | 3 | 2 | 111 |
| 105 | 0.05s | 3 | 3 | 114 |
| 106 | 0.05s | 3 | 1 | 114 |
| 107 | 0.06s | 3 | 0 | 114 |
| 108 | 0.07s | 3 | 2 | 114 |
| 109 | 0.05s | 3 | 1 | 115 |
| 110 | 0.06s | 3 | 0 | 115 |
| 111 | 0.07s | 3 | 0 | 115 |
| 112 | 0.07s | 3 | 1 | 115 |
| 113 | 0.07s | 3 | 1 | 115 |
| 114 | 0.07s | 3 | 1 | 116 |
| 115 | 0.07s | 3 | 1 | 116 |
| 116 | 0.06s | 3 | 2 | 117 |
| 117 | 0.05s | 3 | 3 | 118 |
| 118 | 0.05s | 3 | 1 | 119 |
| 119 | 0.06s | 3 | 0 | 119 |
| 120 | 0.06s | 3 | 0 | 119 |
| 121 | 0.07s | 3 | 0 | 119 |
| 122 | 0.07s | 3 | 1 | 119 |
| 123 | 0.05s | 3 | 2 | 120 |
| 124 | 0.06s | 3 | 1 | 121 |
| 125 | 0.07s | 3 | 1 | 122 |
| 126 | 0.05s | 3 | 2 | 124 |
| 127 | 0.07s | 3 | 1 | 125 |
| 128 | 0.07s | 3 | 0 | 125 |
| 129 | 0.07s | 3 | 1 | 126 |
| 130 | 0.06s | 3 | 1 | 126 |
| 131 | 0.05s | 3 | 2 | 126 |
| 132 | 0.06s | 3 | 0 | 126 |
| 133 | 0.04s | 3 | 1 | 127 |
| 134 | 0.07s | 3 | 2 | 127 |
| 135 | 0.07s | 3 | 1 | 127 |
| 136 | 0.07s | 3 | 0 | 127 |
| 137 | 0.05s | 3 | 1 | 127 |
| 138 | 0.07s | 3 | 0 | 127 |
| 139 | 0.07s | 3 | 1 | 127 |
| 140 | 0.07s | 3 | 1 | 127 |
| 141 | 0.06s | 3 | 1 | 128 |
| 142 | 0.06s | 3 | 0 | 128 |
| 143 | 0.06s | 3 | 0 | 128 |
| 144 | 0.05s | 3 | 1 | 128 |
| 145 | 0.06s | 3 | 0 | 128 |
| 146 | 0.06s | 3 | 0 | 128 |
| 147 | 0.07s | 3 | 1 | 128 |
| 148 | 0.07s | 3 | 1 | 129 |
| 149 | 0.07s | 3 | 1 | 130 |
| 150 | 0.07s | 3 | 1 | 130 |
| 151 | 0.05s | 3 | 2 | 131 |
| 152 | 0.05s | 3 | 1 | 131 |
| 153 | 0.07s | 3 | 2 | 131 |
| 154 | 0.05s | 3 | 0 | 131 |
| 155 | 0.09s | 3 | 1 | 131 |
| 156 | 0.06s | 3 | 1 | 131 |
| 157 | 0.05s | 3 | 1 | 132 |
| 158 | 0.07s | 3 | 1 | 132 |
| 159 | 0.06s | 3 | 1 | 133 |
| 160 | 0.05s | 3 | 0 | 133 |
| 161 | 0.06s | 3 | 1 | 133 |
| 162 | 0.05s | 3 | 2 | 133 |
| 163 | 0.06s | 3 | 2 | 133 |
| 164 | 0.06s | 3 | 0 | 133 |
| 165 | 0.07s | 3 | 1 | 133 |
| 166 | 0.05s | 3 | 0 | 133 |
| 167 | 0.07s | 3 | 1 | 133 |
| 168 | 0.05s | 3 | 0 | 133 |
| 169 | 0.07s | 3 | 1 | 134 |
| 170 | 0.06s | 3 | 2 | 135 |
| 171 | 0.07s | 3 | 0 | 135 |
| 172 | 0.05s | 3 | 0 | 135 |
| 173 | 0.07s | 3 | 0 | 135 |
| 174 | 0.06s | 3 | 0 | 135 |
| 175 | 0.08s | 3 | 1 | 135 |
| 176 | 0.05s | 3 | 1 | 135 |
| 177 | 0.06s | 3 | 1 | 135 |
| 178 | 0.06s | 3 | 1 | 135 |
| 179 | 0.06s | 3 | 0 | 135 |
| 180 | 0.06s | 3 | 0 | 135 |
| 181 | 0.06s | 3 | 1 | 135 |
| 182 | 0.06s | 3 | 0 | 135 |
| 183 | 0.06s | 3 | 3 | 135 |
| 184 | 0.07s | 3 | 1 | 135 |
| 185 | 0.06s | 3 | 0 | 135 |
| 186 | 0.08s | 3 | 0 | 135 |
| 187 | 0.06s | 3 | 1 | 135 |
| 188 | 0.07s | 3 | 0 | 135 |
| 189 | 0.07s | 3 | 0 | 135 |
| 190 | 0.05s | 3 | 2 | 136 |
| 191 | 0.07s | 3 | 1 | 136 |
| 192 | 0.07s | 3 | 0 | 136 |
| 193 | 0.08s | 3 | 1 | 136 |
| 194 | 0.07s | 3 | 0 | 136 |
| 195 | 0.07s | 3 | 0 | 136 |
| 196 | 0.07s | 3 | 0 | 136 |
| 197 | 0.05s | 3 | 2 | 136 |
| 198 | 0.07s | 3 | 0 | 136 |
| 199 | 0.05s | 3 | 2 | 136 |
| 200 | 0.06s | 3 | 1 | 137 |
| 201 | 0.06s | 3 | 0 | 137 |
| 202 | 0.07s | 3 | 1 | 137 |
| 203 | 0.06s | 3 | 0 | 137 |
| 204 | 0.07s | 3 | 0 | 137 |
| 205 | 0.05s | 3 | 1 | 137 |
| 206 | 0.06s | 3 | 0 | 137 |
| 207 | 0.07s | 3 | 1 | 137 |
| 208 | 0.06s | 3 | 1 | 138 |
| 209 | 0.07s | 3 | 0 | 138 |
| 210 | 0.08s | 3 | 0 | 138 |
| 211 | 0.07s | 3 | 1 | 138 |
| 212 | 0.05s | 3 | 0 | 138 |
| 213 | 0.07s | 3 | 1 | 138 |
| 214 | 0.06s | 3 | 0 | 138 |
| 215 | 0.07s | 3 | 1 | 138 |
| 216 | 0.09s | 3 | 0 | 138 |
| 217 | 0.07s | 3 | 0 | 138 |
| 218 | 0.06s | 3 | 0 | 138 |
| 219 | 0.07s | 3 | 1 | 139 |
| 220 | 0.08s | 3 | 0 | 139 |
| 221 | 0.06s | 3 | 1 | 139 |
| 222 | 0.07s | 3 | 3 | 139 |
| 223 | 0.08s | 3 | 1 | 139 |
| 224 | 0.07s | 3 | 0 | 139 |
| 225 | 0.06s | 3 | 0 | 139 |
| 226 | 0.07s | 3 | 0 | 139 |
| 227 | 0.07s | 3 | 1 | 139 |
| 228 | 0.06s | 3 | 1 | 139 |
| 229 | 0.07s | 3 | 0 | 139 |
| 230 | 0.07s | 3 | 1 | 139 |
| 231 | 0.07s | 3 | 2 | 141 |
| 232 | 0.07s | 3 | 2 | 141 |
| 233 | 0.06s | 3 | 0 | 141 |
| 234 | 0.07s | 3 | 1 | 141 |
| 235 | 0.07s | 3 | 0 | 141 |
| 236 | 0.06s | 3 | 0 | 141 |
| 237 | 0.08s | 3 | 0 | 141 |
| 238 | 0.07s | 3 | 2 | 141 |
| 239 | 0.06s | 3 | 1 | 141 |
| 240 | 0.07s | 3 | 0 | 141 |
| 241 | 0.06s | 3 | 0 | 141 |
| 242 | 0.05s | 3 | 1 | 141 |
| 243 | 0.06s | 3 | 0 | 141 |
| 244 | 0.07s | 3 | 0 | 141 |
| 245 | 0.06s | 3 | 0 | 141 |
| 246 | 0.08s | 3 | 2 | 141 |
| 247 | 0.07s | 3 | 0 | 141 |
| 248 | 0.06s | 3 | 0 | 141 |
| 249 | 0.06s | 3 | 2 | 141 |
| 250 | 0.07s | 3 | 0 | 141 |
| 251 | 0.06s | 3 | 0 | 141 |
| 252 | 0.09s | 3 | 0 | 141 |
| 253 | 0.04s | 3 | 2 | 141 |
| 254 | 0.06s | 3 | 0 | 141 |
| 255 | 0.07s | 3 | 1 | 141 |
| 256 | 0.07s | 3 | 1 | 141 |
| 257 | 0.06s | 3 | 0 | 141 |
| 258 | 0.08s | 3 | 1 | 141 |
| 259 | 0.06s | 3 | 1 | 141 |
| 260 | 0.07s | 3 | 1 | 141 |
| 261 | 0.05s | 3 | 0 | 141 |
| 262 | 0.06s | 3 | 1 | 141 |
| 263 | 0.05s | 3 | 0 | 141 |
| 264 | 0.06s | 3 | 0 | 141 |
| 265 | 0.06s | 3 | 0 | 141 |
| 266 | 0.07s | 3 | 1 | 141 |
| 267 | 0.07s | 3 | 2 | 141 |
| 268 | 0.07s | 3 | 0 | 141 |
| 269 | 0.07s | 3 | 0 | 141 |
| 270 | 0.07s | 3 | 1 | 141 |
| 271 | 0.07s | 3 | 1 | 142 |
| 272 | 0.07s | 3 | 0 | 142 |
| 273 | 0.06s | 3 | 0 | 142 |
| 274 | 0.07s | 3 | 0 | 142 |
| 275 | 0.06s | 3 | 0 | 142 |
| 276 | 0.07s | 3 | 0 | 142 |
| 277 | 0.06s | 3 | 0 | 142 |
| 278 | 0.07s | 3 | 0 | 142 |
| 279 | 0.05s | 3 | 1 | 142 |
| 280 | 0.07s | 3 | 0 | 142 |
| 281 | 0.06s | 3 | 0 | 142 |
| 282 | 0.07s | 3 | 0 | 142 |
| 283 | 0.06s | 3 | 1 | 143 |
| 284 | 0.06s | 3 | 0 | 143 |
| 285 | 0.07s | 3 | 0 | 143 |
| 286 | 0.09s | 3 | 1 | 143 |
| 287 | 0.08s | 3 | 0 | 143 |
| 288 | 0.08s | 3 | 0 | 143 |
| 289 | 0.08s | 3 | 0 | 143 |
| 290 | 0.07s | 3 | 0 | 143 |
| 291 | 0.08s | 3 | 0 | 143 |
| 292 | 0.07s | 3 | 0 | 143 |
| 293 | 0.05s | 3 | 0 | 143 |
| 294 | 0.05s | 3 | 0 | 143 |
| 295 | 0.06s | 3 | 0 | 143 |
| 296 | 0.06s | 3 | 0 | 143 |
| 297 | 0.07s | 3 | 0 | 143 |
| 298 | 0.06s | 3 | 0 | 143 |
| 299 | 0.06s | 3 | 0 | 143 |
| 300 | 0.06s | 3 | 3 | 143 |
| 301 | 0.06s | 3 | 1 | 143 |
| 302 | 0.06s | 3 | 0 | 143 |
| 303 | 0.06s | 3 | 1 | 143 |
| 304 | 0.06s | 3 | 0 | 143 |
| 305 | 0.09s | 3 | 0 | 143 |
| 306 | 0.07s | 3 | 0 | 143 |
| 307 | 0.06s | 3 | 0 | 143 |
| 308 | 0.07s | 3 | 0 | 143 |
| 309 | 0.05s | 3 | 0 | 143 |
| 310 | 0.07s | 3 | 1 | 143 |
| 311 | 0.07s | 3 | 0 | 143 |
| 312 | 0.07s | 3 | 0 | 143 |
| 313 | 0.07s | 3 | 0 | 143 |
| 314 | 0.07s | 3 | 1 | 143 |
| 315 | 0.06s | 3 | 0 | 143 |
| 316 | 0.07s | 3 | 0 | 143 |
| 317 | 0.07s | 3 | 0 | 143 |
| 318 | 0.07s | 3 | 1 | 143 |
| 319 | 0.07s | 3 | 0 | 143 |
| 320 | 0.06s | 3 | 0 | 143 |
| 321 | 0.06s | 3 | 0 | 143 |
| 322 | 0.07s | 3 | 0 | 143 |
| 323 | 0.08s | 3 | 0 | 143 |
| 324 | 0.06s | 3 | 0 | 143 |
| 325 | 0.07s | 3 | 0 | 143 |
| 326 | 0.07s | 3 | 1 | 143 |
| 327 | 0.06s | 3 | 1 | 143 |
| 328 | 0.05s | 3 | 1 | 143 |
| 329 | 0.05s | 3 | 0 | 143 |
| 330 | 0.05s | 3 | 1 | 143 |
| 331 | 0.06s | 3 | 0 | 143 |
| 332 | 0.05s | 3 | 0 | 143 |
| 333 | 0.07s | 3 | 0 | 143 |
| 334 | 0.07s | 3 | 0 | 143 |
| 335 | 0.07s | 3 | 0 | 143 |
| 336 | 0.07s | 3 | 0 | 143 |
| 337 | 0.08s | 3 | 0 | 143 |
| 338 | 0.05s | 3 | 0 | 143 |
| 339 | 0.07s | 3 | 0 | 143 |
| 340 | 0.07s | 3 | 0 | 143 |
| 341 | 0.06s | 3 | 0 | 143 |
| 342 | 0.07s | 3 | 0 | 143 |
| 343 | 0.05s | 3 | 0 | 143 |
| 344 | 0.05s | 3 | 1 | 143 |
| 345 | 0.07s | 3 | 0 | 143 |
| 346 | 0.06s | 3 | 0 | 143 |
| 347 | 0.07s | 3 | 1 | 143 |
| 348 | 0.06s | 3 | 0 | 143 |
| 349 | 0.07s | 3 | 0 | 143 |
| 350 | 0.07s | 3 | 1 | 143 |
| 351 | 0.07s | 3 | 0 | 143 |
| 352 | 0.06s | 3 | 0 | 143 |
| 353 | 0.07s | 3 | 0 | 143 |
| 354 | 0.07s | 3 | 0 | 143 |
| 355 | 0.08s | 3 | 0 | 143 |
| 356 | 0.06s | 3 | 0 | 143 |
| 357 | 0.07s | 3 | 0 | 143 |
| 358 | 0.06s | 3 | 0 | 143 |
| 359 | 0.08s | 3 | 0 | 143 |
| 360 | 0.07s | 3 | 0 | 143 |
| 361 | 0.08s | 3 | 2 | 143 |
| 362 | 0.07s | 3 | 0 | 143 |
| 363 | 0.07s | 3 | 0 | 143 |
| 364 | 0.05s | 3 | 3 | 143 |
| 365 | 0.06s | 3 | 2 | 143 |
| 366 | 0.06s | 3 | 0 | 143 |
| 367 | 0.06s | 3 | 2 | 143 |
| 368 | 0.07s | 3 | 0 | 143 |
| 369 | 0.06s | 3 | 0 | 143 |
| 370 | 0.07s | 3 | 0 | 143 |
| 371 | 0.10s | 3 | 1 | 143 |
| 372 | 0.06s | 3 | 1 | 143 |
| 373 | 0.06s | 3 | 0 | 143 |
| 374 | 0.05s | 3 | 0 | 143 |
| 375 | 0.07s | 3 | 0 | 143 |
| 376 | 0.07s | 3 | 0 | 143 |
| 377 | 0.07s | 3 | 0 | 143 |
| 378 | 0.08s | 3 | 1 | 143 |
| 379 | 0.07s | 3 | 1 | 143 |
| 380 | 0.08s | 3 | 0 | 143 |
| 381 | 0.07s | 3 | 0 | 143 |
| 382 | 0.09s | 3 | 0 | 143 |
| 383 | 0.05s | 3 | 0 | 143 |
| 384 | 0.07s | 3 | 0 | 143 |
| 385 | 0.07s | 3 | 0 | 143 |
| 386 | 0.08s | 3 | 0 | 143 |
| 387 | 0.06s | 3 | 0 | 143 |
| 388 | 0.08s | 3 | 1 | 143 |
| 389 | 0.05s | 3 | 1 | 143 |
| 390 | 0.07s | 3 | 1 | 143 |
| 391 | 0.06s | 3 | 1 | 143 |
| 392 | 0.07s | 3 | 1 | 143 |
| 393 | 0.07s | 3 | 0 | 143 |
| 394 | 0.08s | 3 | 0 | 143 |
| 395 | 0.09s | 3 | 1 | 144 |
| 396 | 0.06s | 3 | 0 | 144 |
| 397 | 0.09s | 3 | 1 | 144 |
| 398 | 0.07s | 3 | 0 | 144 |
| 399 | 0.07s | 3 | 0 | 144 |
| 400 | 0.06s | 3 | 0 | 144 |
| 401 | 0.07s | 3 | 1 | 144 |
| 402 | 0.06s | 3 | 0 | 144 |
| 403 | 0.07s | 3 | 0 | 144 |
| 404 | 0.09s | 3 | 0 | 144 |
| 405 | 0.07s | 3 | 0 | 144 |
| 406 | 0.07s | 3 | 1 | 144 |
| 407 | 0.07s | 3 | 0 | 144 |
| 408 | 0.05s | 3 | 1 | 144 |
| 409 | 0.08s | 3 | 0 | 144 |
| 410 | 0.07s | 3 | 1 | 144 |
| 411 | 0.05s | 3 | 0 | 144 |
| 412 | 0.06s | 3 | 0 | 144 |
| 413 | 0.06s | 3 | 0 | 144 |
| 414 | 0.07s | 3 | 1 | 144 |
| 415 | 0.06s | 3 | 0 | 144 |
| 416 | 0.06s | 3 | 0 | 144 |
| 417 | 0.07s | 3 | 0 | 144 |
| 418 | 0.06s | 3 | 2 | 144 |
| 419 | 0.07s | 3 | 0 | 144 |
| 420 | 0.07s | 3 | 0 | 144 |
| 421 | 0.06s | 3 | 0 | 144 |
| 422 | 0.07s | 3 | 0 | 144 |
| 423 | 0.10s | 3 | 0 | 144 |
| 424 | 0.07s | 3 | 0 | 144 |
| 425 | 0.07s | 3 | 0 | 144 |
| 426 | 0.07s | 3 | 1 | 144 |
| 427 | 0.09s | 3 | 0 | 144 |
| 428 | 0.05s | 3 | 1 | 144 |
| 429 | 0.07s | 3 | 0 | 144 |
| 430 | 0.07s | 3 | 0 | 144 |
| 431 | 0.09s | 3 | 0 | 144 |
| 432 | 0.07s | 3 | 0 | 144 |
| 433 | 0.08s | 3 | 0 | 144 |
| 434 | 0.09s | 3 | 0 | 144 |
| 435 | 0.08s | 3 | 1 | 144 |
| 436 | 0.07s | 3 | 0 | 144 |
| 437 | 0.06s | 3 | 1 | 144 |
| 438 | 0.06s | 3 | 1 | 144 |
| 439 | 0.06s | 3 | 0 | 144 |
| 440 | 0.07s | 3 | 0 | 144 |
| 441 | 0.07s | 3 | 0 | 144 |
| 442 | 0.06s | 3 | 0 | 144 |
| 443 | 0.07s | 3 | 1 | 144 |
| 444 | 0.07s | 3 | 0 | 144 |
| 445 | 0.09s | 3 | 0 | 144 |
| 446 | 0.07s | 3 | 0 | 144 |
| 447 | 0.06s | 3 | 0 | 144 |
| 448 | 0.05s | 3 | 0 | 144 |
| 449 | 0.07s | 3 | 0 | 144 |
| 450 | 0.08s | 3 | 0 | 144 |
| 451 | 0.06s | 3 | 0 | 144 |
| 452 | 0.07s | 3 | 2 | 144 |
| 453 | 0.08s | 3 | 0 | 144 |
| 454 | 0.08s | 3 | 0 | 144 |
| 455 | 0.07s | 3 | 0 | 144 |
| 456 | 0.06s | 3 | 1 | 144 |
| 457 | 0.08s | 3 | 0 | 144 |
| 458 | 0.06s | 3 | 0 | 144 |
| 459 | 0.07s | 3 | 2 | 144 |
| 460 | 0.08s | 3 | 0 | 144 |
| 461 | 0.07s | 3 | 0 | 144 |
| 462 | 0.06s | 3 | 1 | 144 |
| 463 | 0.08s | 3 | 0 | 144 |
| 464 | 0.06s | 3 | 0 | 144 |
| 465 | 0.05s | 3 | 0 | 144 |
| 466 | 0.06s | 3 | 0 | 144 |
| 467 | 0.06s | 3 | 1 | 144 |
| 468 | 0.10s | 3 | 0 | 144 |
| 469 | 0.07s | 3 | 0 | 144 |
| 470 | 0.06s | 3 | 0 | 144 |
| 471 | 0.07s | 3 | 0 | 144 |
| 472 | 0.07s | 3 | 0 | 144 |
| 473 | 0.06s | 3 | 0 | 144 |
| 474 | 0.09s | 3 | 0 | 144 |
| 475 | 0.07s | 3 | 0 | 144 |
| 476 | 0.09s | 3 | 0 | 144 |
| 477 | 0.06s | 3 | 0 | 144 |
| 478 | 0.06s | 3 | 1 | 144 |
| 479 | 0.07s | 3 | 0 | 144 |
| 480 | 0.06s | 3 | 0 | 144 |
| 481 | 0.06s | 3 | 1 | 144 |
| 482 | 0.07s | 3 | 0 | 144 |
| 483 | 0.07s | 3 | 0 | 144 |
| 484 | 0.06s | 3 | 1 | 144 |
| 485 | 0.08s | 3 | 0 | 144 |
| 486 | 0.07s | 3 | 0 | 144 |
| 487 | 0.07s | 3 | 0 | 144 |
| 488 | 0.05s | 3 | 0 | 144 |
| 489 | 0.07s | 3 | 1 | 144 |
| 490 | 0.08s | 3 | 0 | 144 |
| 491 | 0.07s | 3 | 0 | 144 |
| 492 | 0.05s | 3 | 0 | 144 |
| 493 | 0.07s | 3 | 0 | 144 |
| 494 | 0.06s | 3 | 0 | 144 |
| 495 | 0.06s | 3 | 0 | 144 |
| 496 | 0.06s | 3 | 0 | 144 |
| 497 | 0.08s | 3 | 0 | 144 |
| 498 | 0.07s | 3 | 0 | 144 |
| 499 | 0.08s | 3 | 0 | 144 |
| 500 | 0.06s | 3 | 0 | 144 |

## The escape region, in plain English

- **tick 1** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 21 escapes are spread across the population rather than concentrated
- **tick 2** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 3** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 23 escapes are spread across the population rather than concentrated
- **tick 4** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 5** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 6** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 25 escapes are spread across the population rather than concentrated
- **tick 7** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 8** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 9** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 10** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 11** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 12** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 13** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 14** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 15** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 16** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 17** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 18** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 19** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 26 escapes are spread across the population rather than concentrated
- **tick 20** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 21** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 22** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 23** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 24** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 27 escapes are spread across the population rather than concentrated
- **tick 25** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 26** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 27** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 28** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 29** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 30** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 31** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 32** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 33** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 34** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 35** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 36** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 37** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 38** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 39** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 10 escapes are spread across the population rather than concentrated
- **tick 40** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 41** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 42** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 43** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 44** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 45** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 46** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 47** *(not reportable)*: no reportable escape region: 2 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 48** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 49** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 22 escapes are spread across the population rather than concentrated
- **tick 50** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 51** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 52** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 53** *(not reportable)*: no reportable escape region: 2 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 54** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 55** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 56** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 57** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 58** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 59** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 60** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 61** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 62** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 63** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 64** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 65** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 34 escapes are spread across the population rather than concentrated
- **tick 66** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 67** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 68** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 69** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 70** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 71** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 72** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 73** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 74** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 75** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 76** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 77** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 78** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 79** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 80** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 81** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 82** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 83** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 84** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 85** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 86** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 87** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 88** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 89** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 90** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 23 escapes are spread across the population rather than concentrated
- **tick 91** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 92** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 93** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 94** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 95** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 96** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 97** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 10 escapes are spread across the population rather than concentrated
- **tick 98** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 99** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 27 escapes are spread across the population rather than concentrated
- **tick 100** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 10 escapes are spread across the population rather than concentrated
- **tick 101** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 102** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 103** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 104** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 105** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 106** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 107** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 108** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 109** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 110** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 111** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 112** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 113** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 21 escapes are spread across the population rather than concentrated
- **tick 114** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 29 escapes are spread across the population rather than concentrated
- **tick 115** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 116** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 117** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 118** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 119** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 120** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 121** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 122** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 123** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 124** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 125** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 126** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 127** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 128** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 129** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 130** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 131** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 132** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 133** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 134** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 135** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 25 escapes are spread across the population rather than concentrated
- **tick 136** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 137** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 138** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 139** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 140** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 141** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 142** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 143** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 144** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 145** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 146** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 147** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 148** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 149** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 150** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 151** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 152** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 153** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 154** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 155** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 32 escapes are spread across the population rather than concentrated
- **tick 156** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 157** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 158** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 10 escapes are spread across the population rather than concentrated
- **tick 159** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 160** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 161** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 162** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 163** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 164** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 165** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 166** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 167** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 10 escapes are spread across the population rather than concentrated
- **tick 168** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 169** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 170** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 171** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 172** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 173** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 174** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 175** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 176** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 177** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 178** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 179** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 180** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 181** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 182** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 183** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 184** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 185** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 186** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 187** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 188** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 189** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 190** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 191** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 192** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 21 escapes are spread across the population rather than concentrated
- **tick 193** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 194** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 195** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 196** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 197** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 198** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 199** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 200** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 201** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 202** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 203** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 10 escapes are spread across the population rather than concentrated
- **tick 204** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 205** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 206** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 207** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 208** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 209** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 210** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 211** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 10 escapes are spread across the population rather than concentrated
- **tick 212** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 213** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 214** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 215** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 216** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 10 escapes are spread across the population rather than concentrated
- **tick 217** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 218** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 219** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 21 escapes are spread across the population rather than concentrated
- **tick 220** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 25 escapes are spread across the population rather than concentrated
- **tick 221** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 222** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 22 escapes are spread across the population rather than concentrated
- **tick 223** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 224** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 225** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 226** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 227** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 228** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 229** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 230** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 231** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 232** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 233** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 234** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 235** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 236** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 237** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 32 escapes are spread across the population rather than concentrated
- **tick 238** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 239** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 240** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 241** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 242** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 243** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 244** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 245** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 246** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 25 escapes are spread across the population rather than concentrated
- **tick 247** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 248** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 249** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 250** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 251** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 252** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 22 escapes are spread across the population rather than concentrated
- **tick 253** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 254** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 255** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 256** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 257** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 258** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 259** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 260** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 261** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 262** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 263** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 264** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 265** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 266** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 267** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 268** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 269** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 270** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 271** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 272** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 273** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 274** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 275** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 276** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 277** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 278** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 279** *(not reportable)*: no reportable escape region: 2 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 280** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 281** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 282** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 283** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 284** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 285** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 286** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 22 escapes are spread across the population rather than concentrated
- **tick 287** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 22 escapes are spread across the population rather than concentrated
- **tick 288** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 289** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 25 escapes are spread across the population rather than concentrated
- **tick 290** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 291** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 292** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 293** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 294** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 295** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 296** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 297** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 298** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 299** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 300** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 301** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 302** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 303** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 10 escapes are spread across the population rather than concentrated
- **tick 304** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 305** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 306** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 307** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 308** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 309** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 310** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 311** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 312** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 313** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 314** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 315** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 316** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 317** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 318** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 319** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 320** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 321** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 322** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 323** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 23 escapes are spread across the population rather than concentrated
- **tick 324** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 325** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 21 escapes are spread across the population rather than concentrated
- **tick 326** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 327** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 328** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 329** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 330** *(not reportable)*: no reportable escape region: 2 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 331** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 332** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 333** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 334** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 335** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 336** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 22 escapes are spread across the population rather than concentrated
- **tick 337** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 338** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 339** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 23 escapes are spread across the population rather than concentrated
- **tick 340** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 341** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 342** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 343** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 344** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 345** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 346** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 347** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 10 escapes are spread across the population rather than concentrated
- **tick 348** *(not reportable)*: no reportable escape region: 2 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 349** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 350** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 351** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 352** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 353** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 354** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 355** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 23 escapes are spread across the population rather than concentrated
- **tick 356** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 357** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 358** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 359** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 25 escapes are spread across the population rather than concentrated
- **tick 360** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 26 escapes are spread across the population rather than concentrated
- **tick 361** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 362** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 363** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 364** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 365** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 366** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 367** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 368** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 25 escapes are spread across the population rather than concentrated
- **tick 369** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 10 escapes are spread across the population rather than concentrated
- **tick 370** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 371** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 372** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 373** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 374** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 375** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 22 escapes are spread across the population rather than concentrated
- **tick 376** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 377** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 378** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 26 escapes are spread across the population rather than concentrated
- **tick 379** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 22 escapes are spread across the population rather than concentrated
- **tick 380** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 381** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 382** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 383** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 384** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 385** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 386** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 387** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 388** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 28 escapes are spread across the population rather than concentrated
- **tick 389** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 390** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 391** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 392** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 393** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 394** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 21 escapes are spread across the population rather than concentrated
- **tick 395** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 23 escapes are spread across the population rather than concentrated
- **tick 396** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 397** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 27 escapes are spread across the population rather than concentrated
- **tick 398** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 10 escapes are spread across the population rather than concentrated
- **tick 399** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 400** *(not reportable)*: no reportable escape region: 4 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 401** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 402** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 403** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 404** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 405** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 406** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 407** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 408** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 409** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 22 escapes are spread across the population rather than concentrated
- **tick 410** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 411** *(not reportable)*: no reportable escape region: 2 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 412** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 413** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 414** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 415** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 416** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 417** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 418** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 419** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 420** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 421** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 422** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 423** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 424** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 425** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 426** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 427** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 32 escapes are spread across the population rather than concentrated
- **tick 428** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 429** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 430** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 431** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 432** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 433** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 434** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 21 escapes are spread across the population rather than concentrated
- **tick 435** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 436** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 437** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 438** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 439** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 440** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 441** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 442** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 443** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 444** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 20 escapes are spread across the population rather than concentrated
- **tick 445** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 32 escapes are spread across the population rather than concentrated
- **tick 446** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 447** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 448** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 449** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 450** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 22 escapes are spread across the population rather than concentrated
- **tick 451** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 452** *(not reportable)*: no reportable escape region: 7 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 453** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 28 escapes are spread across the population rather than concentrated
- **tick 454** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 455** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 456** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 17 escapes are spread across the population rather than concentrated
- **tick 457** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 21 escapes are spread across the population rather than concentrated
- **tick 458** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 459** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 16 escapes are spread across the population rather than concentrated
- **tick 460** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 26 escapes are spread across the population rather than concentrated
- **tick 461** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 462** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 463** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 464** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 465** *(not reportable)*: no reportable escape region: 2 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 466** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 467** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 468** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 469** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 9 escapes are spread across the population rather than concentrated
- **tick 470** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 471** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 472** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 473** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 11 escapes are spread across the population rather than concentrated
- **tick 474** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 28 escapes are spread across the population rather than concentrated
- **tick 475** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 476** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 24 escapes are spread across the population rather than concentrated
- **tick 477** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 478** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 479** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 480** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 481** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 482** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 483** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 12 escapes are spread across the population rather than concentrated
- **tick 484** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 485** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 486** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 15 escapes are spread across the population rather than concentrated
- **tick 487** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 13 escapes are spread across the population rather than concentrated
- **tick 488** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 489** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 490** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 27 escapes are spread across the population rather than concentrated
- **tick 491** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 492** *(not reportable)*: no reportable escape region: 3 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 493** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 14 escapes are spread across the population rather than concentrated
- **tick 494** *(not reportable)*: no reportable escape region: 5 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 495** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 496** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote
- **tick 497** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 18 escapes are spread across the population rather than concentrated
- **tick 498** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 8 escapes are spread across the population rather than concentrated
- **tick 499** *(not reportable)*: escapes are not separable over reviewable features at depth 3: 19 escapes are spread across the population rather than concentrated
- **tick 500** *(not reportable)*: no reportable escape region: 6 escapes is below the 8 floor, so any 'region' fitted here would be an anecdote

## What the attacker LEARNED (the tabular policy, rendered)

This table is why the Level-2 agent is tabular: a judge can read exactly what the attacker learned to do in which situation. A deep policy would be a black box on both sides of the loop, and half the point of the loop is that it is auditable.

| Stage | Last outcome | Budget | Heat | Best tactic | Q |
|---|---|---|---|---|---|
| recon | onward_blocked | high | warm | **escalate_amount** | 2967388.0 |
| establish | step_up | high | warm | **rotate_entity** | 2587755.7 |
| recon | decline | mid | hot | **inherit_trust** | 2232565.4 |
| establish | approve | high | cold | **cash_out** | 2159919.8 |
| recon | none | high | cold | **cash_out** | 2046826.6 |
| establish | onward_blocked | high | hot | **deescalate_amount** | 2036960.9 |
| establish | credit_landed | high | cold | **probe** | 1965572.7 |
| establish | account_frozen | mid | warm | **rotate_entity** | 1946018.8 |
| recon | credit_landed | high | warm | **deescalate_amount** | 1922891.3 |
| establish | decline | high | hot | **deescalate_amount** | 1905938.2 |
| establish | decline | high | warm | **escalate_amount** | 1897276.0 |
| establish | account_frozen | high | warm | **escalate_amount** | 1847462.6 |

## Sibling transfer recall — the anti-tautology number

| Tick | Mutated slot | Tier | Closed recall | Sibling recall | Wilson 95% CI | n |
|---|---|---|---|---|---|---|
| 1 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 2 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 3 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 4 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 5 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 6 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 7 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 8 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 9 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 10 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 11 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 12 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 13 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 14 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 15 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 16 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 17 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 18 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 19 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 20 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 21 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 22 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 23 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 24 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 25 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 26 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 27 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 28 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 29 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 30 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 31 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 32 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 33 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 34 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 35 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 36 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 37 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 38 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 39 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 40 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 41 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 42 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 43 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 44 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 45 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 46 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 47 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 48 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.900 | [0.769, 0.960] | 40 |
| 49 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 50 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 51 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.900 | [0.769, 0.960] | 40 |
| 52 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 53 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 54 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 55 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 56 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 57 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 58 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 59 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 60 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 61 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 62 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 63 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 64 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 65 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 66 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 67 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 68 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 69 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 70 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 71 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 72 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 73 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 74 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 75 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 76 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 77 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 78 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 79 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.900 | [0.769, 0.960] | 40 |
| 80 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 81 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 82 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 83 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 84 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 85 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 86 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 87 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 88 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 89 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 90 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 91 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 92 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 93 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 94 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 95 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 96 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 97 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 98 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 99 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 100 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 101 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 102 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 103 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 104 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 105 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 106 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 107 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 108 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 109 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 110 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 111 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 112 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 113 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 114 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 115 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 116 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 117 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 118 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 119 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 120 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 121 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 122 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 123 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 124 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 125 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 126 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 127 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 128 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 129 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 130 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.900 | [0.769, 0.960] | 40 |
| 131 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 132 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 133 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 134 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 135 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 136 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 137 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 138 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 139 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 140 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 141 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 142 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 143 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 144 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 145 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 146 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 147 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 148 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 149 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 150 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 151 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 152 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 153 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 154 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 155 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 156 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 157 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 158 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 159 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 160 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 161 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 162 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 163 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 164 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 165 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 166 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 167 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 168 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 169 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 170 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 171 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 172 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 173 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 174 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 175 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 176 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 177 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 178 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 179 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 180 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 181 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 182 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 183 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 184 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 185 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 186 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 187 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 188 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 189 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 190 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 191 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 192 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 193 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 194 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 195 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 196 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 197 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 198 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 199 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 200 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 201 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 202 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 203 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 204 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 205 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 206 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 207 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 208 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 209 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 210 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 211 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 212 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 213 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 214 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 215 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 216 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 217 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 218 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 219 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 220 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 221 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 222 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 223 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 224 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 225 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 226 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 227 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 228 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 229 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 230 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 231 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.900 | [0.769, 0.960] | 40 |
| 232 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 233 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 234 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 235 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 236 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 237 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 238 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 239 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 240 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 241 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 242 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 243 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 244 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 245 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 246 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 247 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 248 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 249 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 250 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 251 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 252 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 253 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 254 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 255 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.900 | [0.769, 0.960] | 40 |
| 256 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 257 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 258 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 259 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 260 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 261 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 262 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 263 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 264 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 265 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 266 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 267 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 268 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 269 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 270 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 271 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 272 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 273 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 274 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 275 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 276 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 277 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 278 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 279 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 280 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 281 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 282 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 283 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 284 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 285 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 286 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 287 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 288 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 289 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 290 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 291 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.900 | [0.769, 0.960] | 40 |
| 292 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 293 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 294 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 295 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 296 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 297 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 298 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 299 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 300 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 301 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 302 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.875 | [0.739, 0.945] | 40 |
| 303 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 304 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 305 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 306 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 307 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 308 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 309 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 310 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 311 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 312 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 313 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 314 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 315 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 316 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 317 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 318 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 319 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 320 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 321 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 322 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 323 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 324 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 325 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 326 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 327 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 328 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 329 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 330 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 331 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 332 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 333 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 334 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 335 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 336 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 337 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 338 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 339 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 340 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 341 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 342 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 343 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 344 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 345 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 346 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 347 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 348 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 349 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 350 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 351 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 352 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 353 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 354 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 355 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 356 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 357 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 358 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 359 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 360 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 361 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 362 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 363 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 364 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 365 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 366 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 367 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 368 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 369 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 370 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 371 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 372 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 373 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 374 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 375 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 376 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 377 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 378 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 379 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 380 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 381 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 382 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 383 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 384 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 385 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 386 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 387 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 388 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 389 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 390 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 391 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 392 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 393 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 394 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 395 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 396 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 397 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 398 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 399 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 400 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 401 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 402 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 403 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 404 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 405 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 406 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 407 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 408 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 409 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 410 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 411 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 412 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 413 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 414 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 415 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 416 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.900 | [0.769, 0.960] | 40 |
| 417 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 418 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 419 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 420 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 421 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 422 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.900 | [0.769, 0.960] | 40 |
| 423 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 424 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 425 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 426 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 427 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 428 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 429 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 430 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 431 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 432 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 433 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 434 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 435 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 436 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 437 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 438 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 439 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 440 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 441 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 442 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 443 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 444 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 445 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 446 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 447 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 448 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 449 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 450 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 451 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 452 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 453 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 454 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 455 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 456 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 457 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 458 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 459 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 460 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 461 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 462 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 463 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 464 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 465 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 466 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 467 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 468 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 469 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 470 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 471 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 472 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 473 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 474 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 475 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |
| 476 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 477 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 478 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 479 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.900 | [0.769, 0.960] | 40 |
| 480 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 481 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 482 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 483 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 484 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 485 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 486 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 487 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.925 | [0.801, 0.974] | 40 |
| 488 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 489 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 490 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 491 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 492 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 493 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 494 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 495 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.975 | [0.871, 0.996] | 40 |
| 496 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 497 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 498 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 499 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 1.000 | [0.912, 1.000] | 40 |
| 500 | EVASION | headline: cross-cell, EVASION-mutated | 0.974 | 0.950 | [0.835, 0.986] | 40 |

PRE-RETRAIN action table, captured before the retrain and passed through unchanged. Re-tuning the threshold after retraining would let a recall gain be bought with false positives and presented as generalisation.


This may land near zero and we publish it if it does. It is the single metric that distinguishes learning from memorisation.


## Search claim

MAP-Elites optimisation at 10.4 evaluations per occupied cell — below the >=25 budget, so selection pressure is weaker than intended and the coverage trend carries less weight.


## Composer

```json
{
  "mode": "cached",
  "blind_composer": false,
  "n_live_calls": 0,
  "max_live_calls": 250,
  "n_cache_hits": 1488,
  "n_heuristic_fallbacks": 12,
  "n_rejected_by_dual_use_lint": 0,
  "reject_log": {
    "n_entries": 13616,
    "n_rejected": 0,
    "rejections_per_rule": {},
    "n_rules": 12
  },
  "invocation_policy": "ONE call per TICK, only on a Gap Miner escape-region report. Never per transaction: per-transaction adaptation is what the bandit does, better and three orders of magnitude more cheaply.",
  "network_policy": "LLM_MODE=cached is the DEFAULT and never touches the network. The demo path is offline. If the key or the budget is exhausted the loop runs from cache and the archive stops growing \u2014 a degraded run, not a broken one.",
  "heuristic_note": "Proposals sourced `heuristic` came from the deterministic grammar-aware fallback, which is a WEAKER variation operator than an LLM. Labelled so a coverage figure is never read as an LLM result when it was not."
}
```


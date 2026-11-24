Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory)

# Held-command arm, base: command held 12 ticks v closed loop

1000 games per cell on T44's starts; control: every cell (60) equals the reference game for game at hold 1 (1000 games each).

| Team | Script | Opponent | Closed loop wins | Held wins | Held only | Closed only | Games that differ |
|---|---|---|---|---|---|---|---|
| strike | strike_straight | guard_parked_centre | 466/1000 | 466/1000 | 0 | 0 | 3 |
| strike | strike_straight | guard_parked_ring | 477/1000 | 477/1000 | 0 | 0 | 2 |
| strike | strike_straight | guard_mark_edge | 192/1000 | 192/1000 | 0 | 0 | 1 |
| strike | strike_straight | guard_mirror | 204/1000 | 204/1000 | 0 | 0 | 0 |
| strike | strike_straight | guard_field | 284/1000 | 284/1000 | 0 | 0 | 0 |
| strike | strike_flank | guard_parked_centre | 550/1000 | 626/1000 | 78 | 2 | 683 |
| strike | strike_flank | guard_parked_ring | 523/1000 | 581/1000 | 60 | 2 | 604 |
| strike | strike_flank | guard_mark_edge | 113/1000 | 109/1000 | 14 | 18 | 661 |
| strike | strike_flank | guard_mirror | 136/1000 | 152/1000 | 31 | 15 | 757 |
| strike | strike_flank | guard_field | 192/1000 | 180/1000 | 2 | 14 | 489 |
| strike | strike_high | guard_parked_centre | 534/1000 | 531/1000 | 1 | 4 | 1000 |
| strike | strike_high | guard_parked_ring | 546/1000 | 543/1000 | 0 | 3 | 1000 |
| strike | strike_high | guard_mark_edge | 150/1000 | 89/1000 | 40 | 101 | 1000 |
| strike | strike_high | guard_mirror | 152/1000 | 87/1000 | 40 | 105 | 1000 |
| strike | strike_high | guard_field | 266/1000 | 205/1000 | 0 | 61 | 1000 |
| strike | strike_low | guard_parked_centre | 570/1000 | 570/1000 | 0 | 0 | 1000 |
| strike | strike_low | guard_parked_ring | 576/1000 | 576/1000 | 0 | 0 | 1000 |
| strike | strike_low | guard_mark_edge | 156/1000 | 96/1000 | 33 | 93 | 997 |
| strike | strike_low | guard_mirror | 153/1000 | 99/1000 | 33 | 87 | 998 |
| strike | strike_low | guard_field | 261/1000 | 221/1000 | 0 | 40 | 1000 |
| strike | strike_sacrifice | guard_parked_centre | 475/1000 | 460/1000 | 4 | 19 | 986 |
| strike | strike_sacrifice | guard_parked_ring | 497/1000 | 471/1000 | 0 | 26 | 983 |
| strike | strike_sacrifice | guard_mark_edge | 40/1000 | 39/1000 | 11 | 12 | 954 |
| strike | strike_sacrifice | guard_mirror | 73/1000 | 67/1000 | 14 | 20 | 967 |
| strike | strike_sacrifice | guard_field | 138/1000 | 98/1000 | 0 | 40 | 822 |
| strike | strike_converge | guard_parked_centre | 14/1000 | 32/1000 | 29 | 11 | 997 |
| strike | strike_converge | guard_parked_ring | 17/1000 | 52/1000 | 47 | 12 | 998 |
| strike | strike_converge | guard_mark_edge | 26/1000 | 28/1000 | 20 | 18 | 958 |
| strike | strike_converge | guard_mirror | 32/1000 | 28/1000 | 16 | 20 | 962 |
| strike | strike_converge | guard_field | 129/1000 | 89/1000 | 0 | 40 | 884 |
| guard | guard_parked_centre | strike_straight | 534/1000 | 534/1000 | 0 | 0 | 0 |
| guard | guard_parked_centre | strike_flank | 450/1000 | 450/1000 | 0 | 0 | 0 |
| guard | guard_parked_centre | strike_high | 466/1000 | 466/1000 | 0 | 0 | 0 |
| guard | guard_parked_centre | strike_low | 430/1000 | 430/1000 | 0 | 0 | 0 |
| guard | guard_parked_centre | strike_sacrifice | 525/1000 | 525/1000 | 0 | 0 | 0 |
| guard | guard_parked_centre | strike_converge | 986/1000 | 986/1000 | 0 | 0 | 0 |
| guard | guard_parked_ring | strike_straight | 523/1000 | 521/1000 | 0 | 2 | 58 |
| guard | guard_parked_ring | strike_flank | 477/1000 | 482/1000 | 5 | 0 | 183 |
| guard | guard_parked_ring | strike_high | 454/1000 | 454/1000 | 0 | 0 | 28 |
| guard | guard_parked_ring | strike_low | 424/1000 | 424/1000 | 0 | 0 | 21 |
| guard | guard_parked_ring | strike_sacrifice | 503/1000 | 501/1000 | 0 | 2 | 308 |
| guard | guard_parked_ring | strike_converge | 983/1000 | 983/1000 | 0 | 0 | 26 |
| guard | guard_mark_edge | strike_straight | 808/1000 | 793/1000 | 13 | 28 | 392 |
| guard | guard_mark_edge | strike_flank | 887/1000 | 871/1000 | 15 | 31 | 551 |
| guard | guard_mark_edge | strike_high | 850/1000 | 838/1000 | 20 | 32 | 424 |
| guard | guard_mark_edge | strike_low | 844/1000 | 844/1000 | 22 | 22 | 415 |
| guard | guard_mark_edge | strike_sacrifice | 960/1000 | 941/1000 | 13 | 32 | 771 |
| guard | guard_mark_edge | strike_converge | 974/1000 | 949/1000 | 18 | 43 | 726 |
| guard | guard_mirror | strike_straight | 796/1000 | 792/1000 | 17 | 21 | 387 |
| guard | guard_mirror | strike_flank | 864/1000 | 846/1000 | 30 | 48 | 851 |
| guard | guard_mirror | strike_high | 848/1000 | 832/1000 | 15 | 31 | 420 |
| guard | guard_mirror | strike_low | 847/1000 | 841/1000 | 25 | 31 | 435 |
| guard | guard_mirror | strike_sacrifice | 927/1000 | 922/1000 | 22 | 27 | 916 |
| guard | guard_mirror | strike_converge | 968/1000 | 940/1000 | 17 | 45 | 903 |
| guard | guard_field | strike_straight | 716/1000 | 710/1000 | 0 | 6 | 12 |
| guard | guard_field | strike_flank | 808/1000 | 792/1000 | 0 | 16 | 116 |
| guard | guard_field | strike_high | 734/1000 | 727/1000 | 0 | 7 | 45 |
| guard | guard_field | strike_low | 739/1000 | 734/1000 | 2 | 7 | 36 |
| guard | guard_field | strike_sacrifice | 862/1000 | 836/1000 | 2 | 28 | 287 |
| guard | guard_field | strike_converge | 871/1000 | 842/1000 | 1 | 30 | 427 |

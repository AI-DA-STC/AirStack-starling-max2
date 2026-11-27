Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory)

# Run 0 constant-choice ceiling, skills route: Strike v guard_parked_centre (3v3, base)

1000 games per choice on T44's starts, the choice held every 12-tick decision for the whole game; device cpu; pipeline check, not for flight; of record: True.

- Best constant choice: **free:strike_low+strike_low+strike_low** 984/1000 (95 % CI 0.974-0.990)
- Untrained team (free:strike_straight+strike_straight+strike_straight): 899/1000, Wilson upper bound 0.9162
- Mark rule: (984 - 0.05 x 1000) / 1000 = 934/1000 = **0.934**; above the untrained upper bound: True (**MARK_SET**); the gate file's mark now: None

| Choice | Flies (slot 0, 1, 2) | Reaches | 95 % CI | Holds | Unfinished |
|---|---|---|---|---|---|
| free:strike_low+strike_low+strike_low | strike_low, strike_low, strike_low | 984/1000 | 0.974-0.990 | 16 | 0 |
| free:strike_low+strike_high+strike_low | strike_low, strike_high, strike_low | 981/1000 | 0.971-0.988 | 19 | 0 |
| free:strike_low+strike_low+strike_high | strike_low, strike_low, strike_high | 981/1000 | 0.971-0.988 | 19 | 0 |
| free:strike_low+strike_high+strike_high | strike_low, strike_high, strike_high | 978/1000 | 0.967-0.985 | 22 | 0 |
| free:strike_high+strike_low+strike_low | strike_high, strike_low, strike_low | 977/1000 | 0.966-0.985 | 23 | 0 |
| free:strike_high+strike_high+strike_low | strike_high, strike_high, strike_low | 974/1000 | 0.962-0.982 | 26 | 0 |
| free:strike_high+strike_low+strike_high | strike_high, strike_low, strike_high | 972/1000 | 0.960-0.981 | 28 | 0 |
| free:strike_low+strike_straight+strike_low | strike_low, strike_straight, strike_low | 971/1000 | 0.959-0.980 | 29 | 0 |
| free:strike_high+strike_high+strike_high | strike_high, strike_high, strike_high | 969/1000 | 0.956-0.978 | 31 | 0 |
| free:strike_straight+strike_low+strike_low | strike_straight, strike_low, strike_low | 967/1000 | 0.954-0.976 | 33 | 0 |
| free:strike_low+strike_low+strike_straight | strike_low, strike_low, strike_straight | 967/1000 | 0.954-0.976 | 33 | 0 |
| free:strike_low+strike_straight+strike_high | strike_low, strike_straight, strike_high | 966/1000 | 0.953-0.976 | 34 | 0 |
| free:strike_low+strike_high+strike_straight | strike_low, strike_high, strike_straight | 964/1000 | 0.951-0.974 | 36 | 0 |
| free:strike_straight+strike_high+strike_low | strike_straight, strike_high, strike_low | 962/1000 | 0.948-0.972 | 38 | 0 |
| free:strike_high+strike_straight+strike_low | strike_high, strike_straight, strike_low | 962/1000 | 0.948-0.972 | 38 | 0 |
| free:strike_low+strike_flank+strike_low | strike_low, strike_flank, strike_low | 960/1000 | 0.946-0.970 | 40 | 0 |
| free:strike_high+strike_straight+strike_high | strike_high, strike_straight, strike_high | 955/1000 | 0.940-0.966 | 45 | 0 |
| free:strike_high+strike_low+strike_straight | strike_high, strike_low, strike_straight | 955/1000 | 0.940-0.966 | 45 | 0 |
| free:strike_straight+strike_low+strike_high | strike_straight, strike_low, strike_high | 954/1000 | 0.939-0.965 | 46 | 0 |
| free:strike_high+strike_high+strike_straight | strike_high, strike_high, strike_straight | 952/1000 | 0.937-0.964 | 48 | 0 |
| free:strike_low+strike_straight+strike_straight | strike_low, strike_straight, strike_straight | 949/1000 | 0.934-0.961 | 51 | 0 |
| free:strike_straight+strike_high+strike_high | strike_straight, strike_high, strike_high | 948/1000 | 0.932-0.960 | 52 | 0 |
| free:strike_flank+strike_low+strike_low | strike_flank, strike_low, strike_low | 948/1000 | 0.932-0.960 | 52 | 0 |
| free:strike_low+strike_flank+strike_high | strike_low, strike_flank, strike_high | 947/1000 | 0.931-0.959 | 53 | 0 |
| free:strike_straight+strike_straight+strike_low | strike_straight, strike_straight, strike_low | 946/1000 | 0.930-0.958 | 54 | 0 |
| free:strike_high+strike_flank+strike_low | strike_high, strike_flank, strike_low | 946/1000 | 0.930-0.958 | 54 | 0 |
| free:strike_low+strike_low+strike_flank | strike_low, strike_low, strike_flank | 944/1000 | 0.928-0.957 | 56 | 0 |
| free:strike_flank+strike_high+strike_low | strike_flank, strike_high, strike_low | 938/1000 | 0.921-0.951 | 62 | 0 |
| free:strike_straight+strike_low+strike_straight | strike_straight, strike_low, strike_straight | 934/1000 | 0.917-0.948 | 66 | 0 |
| free:strike_low+strike_high+strike_flank | strike_low, strike_high, strike_flank | 934/1000 | 0.917-0.948 | 66 | 0 |
| free:strike_high+strike_straight+strike_straight | strike_high, strike_straight, strike_straight | 933/1000 | 0.916-0.947 | 67 | 0 |
| free:strike_flank+strike_low+strike_high | strike_flank, strike_low, strike_high | 931/1000 | 0.914-0.945 | 69 | 0 |
| free:strike_straight+strike_straight+strike_high | strike_straight, strike_straight, strike_high | 930/1000 | 0.912-0.944 | 70 | 0 |
| free:strike_high+strike_flank+strike_high | strike_high, strike_flank, strike_high | 928/1000 | 0.910-0.942 | 72 | 0 |
| free:strike_high+strike_low+strike_flank | strike_high, strike_low, strike_flank | 928/1000 | 0.910-0.942 | 72 | 0 |
| free:strike_straight+strike_high+strike_straight | strike_straight, strike_high, strike_straight | 927/1000 | 0.909-0.942 | 73 | 0 |
| free:strike_straight+strike_flank+strike_low | strike_straight, strike_flank, strike_low | 923/1000 | 0.905-0.938 | 77 | 0 |
| free:strike_low+strike_flank+strike_straight | strike_low, strike_flank, strike_straight | 920/1000 | 0.902-0.935 | 80 | 0 |
| free:strike_flank+strike_high+strike_high | strike_flank, strike_high, strike_high | 918/1000 | 0.899-0.933 | 82 | 0 |
| free:strike_high+strike_high+strike_flank | strike_high, strike_high, strike_flank | 918/1000 | 0.899-0.933 | 82 | 0 |
| free:strike_flank+strike_straight+strike_low | strike_flank, strike_straight, strike_low | 914/1000 | 0.895-0.930 | 86 | 0 |
| free:strike_low+strike_straight+strike_flank | strike_low, strike_straight, strike_flank | 911/1000 | 0.892-0.927 | 89 | 0 |
| free:strike_flank+strike_low+strike_straight | strike_flank, strike_low, strike_straight | 903/1000 | 0.883-0.920 | 97 | 0 |
| free:strike_straight+strike_low+strike_flank | strike_straight, strike_low, strike_flank | 901/1000 | 0.881-0.918 | 99 | 0 |
| free:strike_straight+strike_straight+strike_straight | strike_straight, strike_straight, strike_straight | 899/1000 | 0.879-0.916 | 101 | 0 |
| free:strike_high+strike_flank+strike_straight | strike_high, strike_flank, strike_straight | 895/1000 | 0.874-0.913 | 105 | 0 |
| free:strike_straight+strike_flank+strike_high | strike_straight, strike_flank, strike_high | 893/1000 | 0.872-0.911 | 107 | 0 |
| free:strike_flank+strike_high+strike_straight | strike_flank, strike_high, strike_straight | 889/1000 | 0.868-0.907 | 111 | 0 |
| free:strike_high+strike_straight+strike_flank | strike_high, strike_straight, strike_flank | 887/1000 | 0.866-0.905 | 113 | 0 |
| free:strike_flank+strike_straight+strike_high | strike_flank, strike_straight, strike_high | 886/1000 | 0.865-0.904 | 114 | 0 |
| free:strike_straight+strike_high+strike_flank | strike_straight, strike_high, strike_flank | 885/1000 | 0.864-0.903 | 115 | 0 |
| free:strike_flank+strike_flank+strike_low | strike_flank, strike_flank, strike_low | 874/1000 | 0.852-0.893 | 126 | 0 |
| free:strike_low+strike_flank+strike_flank | strike_low, strike_flank, strike_flank | 869/1000 | 0.847-0.889 | 131 | 0 |
| free:strike_flank+strike_low+strike_flank | strike_flank, strike_low, strike_flank | 858/1000 | 0.835-0.878 | 142 | 0 |
| free:strike_straight+strike_flank+strike_straight | strike_straight, strike_flank, strike_straight | 848/1000 | 0.824-0.869 | 152 | 0 |
| free:strike_flank+strike_straight+strike_straight | strike_flank, strike_straight, strike_straight | 846/1000 | 0.822-0.867 | 154 | 0 |
| free:strike_straight+strike_straight+strike_flank | strike_straight, strike_straight, strike_flank | 843/1000 | 0.819-0.864 | 157 | 0 |
| free:strike_flank+strike_high+strike_flank | strike_flank, strike_high, strike_flank | 833/1000 | 0.809-0.855 | 167 | 0 |
| free:strike_flank+strike_flank+strike_high | strike_flank, strike_flank, strike_high | 831/1000 | 0.807-0.853 | 169 | 0 |
| free:strike_high+strike_flank+strike_flank | strike_high, strike_flank, strike_flank | 829/1000 | 0.804-0.851 | 171 | 0 |
| team:strike_sacrifice | strike_sacrifice, strike_sacrifice, strike_sacrifice | 790/1000 | 0.764-0.814 | 210 | 0 |
| free:strike_flank+strike_flank+strike_straight | strike_flank, strike_flank, strike_straight | 772/1000 | 0.745-0.797 | 228 | 0 |
| free:strike_straight+strike_flank+strike_flank | strike_straight, strike_flank, strike_flank | 770/1000 | 0.743-0.795 | 230 | 0 |
| free:strike_flank+strike_straight+strike_flank | strike_flank, strike_straight, strike_flank | 769/1000 | 0.742-0.794 | 231 | 0 |
| free:strike_flank+strike_flank+strike_flank | strike_flank, strike_flank, strike_flank | 669/1000 | 0.639-0.697 | 331 | 0 |
| team:strike_converge | strike_converge, strike_converge, strike_converge | 327/1000 | 0.299-0.357 | 673 | 0 |

Controls: ctl_one_script_choices_are_reference PASS; ctl_choice_log_is_the_fixed_choice PASS; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS

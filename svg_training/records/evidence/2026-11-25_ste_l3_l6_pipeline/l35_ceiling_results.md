Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory)

# Run 0 constant-choice ceiling, skills route: Strike v guard_parked_centre (3v3, base)

1000 games per choice on T44's starts, the choice held every 12-tick decision for the whole game; device cpu; pipeline check, not for flight; of record: True.

- Best constant choice: **free:strike_low+strike_low+strike_straight** 604/1000 (95 % CI 0.573-0.634)
- Untrained team (free:strike_straight+strike_straight+strike_straight): 466/1000, Wilson upper bound 0.4970
- Mark rule: (604 - 0.05 x 1000) / 1000 = 554/1000 = **0.554**; above the untrained upper bound: True (**MARK_SET**); the gate file's mark now: 0.9

| Choice | Flies (slot 0, 1, 2) | Reaches | 95 % CI | Holds | Unfinished |
|---|---|---|---|---|---|
| free:strike_low+strike_low+strike_straight | strike_low, strike_low, strike_straight | 604/1000 | 0.573-0.634 | 396 | 0 |
| free:strike_low+strike_low+strike_flank | strike_low, strike_low, strike_flank | 603/1000 | 0.572-0.633 | 397 | 0 |
| free:strike_low+strike_flank+strike_flank | strike_low, strike_flank, strike_flank | 601/1000 | 0.570-0.631 | 399 | 0 |
| free:strike_low+strike_flank+strike_low | strike_low, strike_flank, strike_low | 597/1000 | 0.566-0.627 | 403 | 0 |
| free:strike_low+strike_straight+strike_low | strike_low, strike_straight, strike_low | 595/1000 | 0.564-0.625 | 405 | 0 |
| free:strike_straight+strike_low+strike_low | strike_straight, strike_low, strike_low | 590/1000 | 0.559-0.620 | 410 | 0 |
| free:strike_flank+strike_low+strike_flank | strike_flank, strike_low, strike_flank | 588/1000 | 0.557-0.618 | 412 | 0 |
| free:strike_flank+strike_low+strike_low | strike_flank, strike_low, strike_low | 586/1000 | 0.555-0.616 | 414 | 0 |
| free:strike_low+strike_high+strike_flank | strike_low, strike_high, strike_flank | 585/1000 | 0.554-0.615 | 415 | 0 |
| free:strike_high+strike_low+strike_flank | strike_high, strike_low, strike_flank | 580/1000 | 0.549-0.610 | 420 | 0 |
| free:strike_low+strike_straight+strike_flank | strike_low, strike_straight, strike_flank | 579/1000 | 0.548-0.609 | 421 | 0 |
| free:strike_high+strike_low+strike_straight | strike_high, strike_low, strike_straight | 578/1000 | 0.547-0.608 | 422 | 0 |
| free:strike_low+strike_flank+strike_straight | strike_low, strike_flank, strike_straight | 578/1000 | 0.547-0.608 | 422 | 0 |
| free:strike_flank+strike_flank+strike_low | strike_flank, strike_flank, strike_low | 577/1000 | 0.546-0.607 | 423 | 0 |
| free:strike_low+strike_flank+strike_high | strike_low, strike_flank, strike_high | 577/1000 | 0.546-0.607 | 423 | 0 |
| free:strike_high+strike_flank+strike_low | strike_high, strike_flank, strike_low | 575/1000 | 0.544-0.605 | 425 | 0 |
| free:strike_low+strike_high+strike_straight | strike_low, strike_high, strike_straight | 574/1000 | 0.543-0.604 | 426 | 0 |
| free:strike_low+strike_straight+strike_straight | strike_low, strike_straight, strike_straight | 573/1000 | 0.542-0.603 | 427 | 0 |
| free:strike_low+strike_straight+strike_high | strike_low, strike_straight, strike_high | 573/1000 | 0.542-0.603 | 427 | 0 |
| free:strike_flank+strike_high+strike_low | strike_flank, strike_high, strike_low | 571/1000 | 0.540-0.601 | 429 | 0 |
| free:strike_low+strike_low+strike_low | strike_low, strike_low, strike_low | 570/1000 | 0.539-0.600 | 430 | 0 |
| free:strike_straight+strike_low+strike_flank | strike_straight, strike_low, strike_flank | 567/1000 | 0.536-0.597 | 433 | 0 |
| free:strike_high+strike_flank+strike_flank | strike_high, strike_flank, strike_flank | 566/1000 | 0.535-0.596 | 434 | 0 |
| free:strike_flank+strike_high+strike_flank | strike_flank, strike_high, strike_flank | 565/1000 | 0.534-0.595 | 435 | 0 |
| free:strike_low+strike_low+strike_high | strike_low, strike_low, strike_high | 565/1000 | 0.534-0.595 | 435 | 0 |
| free:strike_straight+strike_high+strike_low | strike_straight, strike_high, strike_low | 564/1000 | 0.533-0.594 | 436 | 0 |
| free:strike_flank+strike_low+strike_high | strike_flank, strike_low, strike_high | 564/1000 | 0.533-0.594 | 436 | 0 |
| free:strike_straight+strike_low+strike_high | strike_straight, strike_low, strike_high | 563/1000 | 0.532-0.593 | 437 | 0 |
| free:strike_high+strike_straight+strike_low | strike_high, strike_straight, strike_low | 561/1000 | 0.530-0.591 | 439 | 0 |
| free:strike_low+strike_high+strike_low | strike_low, strike_high, strike_low | 561/1000 | 0.530-0.591 | 439 | 0 |
| free:strike_straight+strike_flank+strike_low | strike_straight, strike_flank, strike_low | 560/1000 | 0.529-0.590 | 440 | 0 |
| free:strike_high+strike_high+strike_flank | strike_high, strike_high, strike_flank | 560/1000 | 0.529-0.590 | 440 | 0 |
| free:strike_high+strike_low+strike_low | strike_high, strike_low, strike_low | 560/1000 | 0.529-0.590 | 440 | 0 |
| free:strike_flank+strike_low+strike_straight | strike_flank, strike_low, strike_straight | 555/1000 | 0.524-0.586 | 445 | 0 |
| free:strike_low+strike_high+strike_high | strike_low, strike_high, strike_high | 554/1000 | 0.523-0.585 | 446 | 0 |
| free:strike_flank+strike_straight+strike_low | strike_flank, strike_straight, strike_low | 553/1000 | 0.522-0.584 | 447 | 0 |
| free:strike_straight+strike_low+strike_straight | strike_straight, strike_low, strike_straight | 550/1000 | 0.519-0.581 | 450 | 0 |
| free:strike_flank+strike_flank+strike_flank | strike_flank, strike_flank, strike_flank | 550/1000 | 0.519-0.581 | 450 | 0 |
| free:strike_straight+strike_straight+strike_low | strike_straight, strike_straight, strike_low | 549/1000 | 0.518-0.580 | 451 | 0 |
| free:strike_high+strike_high+strike_low | strike_high, strike_high, strike_low | 549/1000 | 0.518-0.580 | 451 | 0 |
| free:strike_flank+strike_high+strike_high | strike_flank, strike_high, strike_high | 548/1000 | 0.517-0.579 | 452 | 0 |
| free:strike_high+strike_low+strike_high | strike_high, strike_low, strike_high | 547/1000 | 0.516-0.578 | 453 | 0 |
| free:strike_high+strike_flank+strike_high | strike_high, strike_flank, strike_high | 546/1000 | 0.515-0.577 | 454 | 0 |
| free:strike_high+strike_high+strike_straight | strike_high, strike_high, strike_straight | 544/1000 | 0.513-0.575 | 456 | 0 |
| free:strike_flank+strike_flank+strike_high | strike_flank, strike_flank, strike_high | 540/1000 | 0.509-0.571 | 460 | 0 |
| free:strike_high+strike_flank+strike_straight | strike_high, strike_flank, strike_straight | 536/1000 | 0.505-0.567 | 464 | 0 |
| free:strike_straight+strike_high+strike_high | strike_straight, strike_high, strike_high | 535/1000 | 0.504-0.566 | 465 | 0 |
| free:strike_high+strike_high+strike_high | strike_high, strike_high, strike_high | 534/1000 | 0.503-0.565 | 466 | 0 |
| free:strike_straight+strike_high+strike_flank | strike_straight, strike_high, strike_flank | 533/1000 | 0.502-0.564 | 467 | 0 |
| free:strike_high+strike_straight+strike_flank | strike_high, strike_straight, strike_flank | 531/1000 | 0.500-0.562 | 469 | 0 |
| free:strike_high+strike_straight+strike_high | strike_high, strike_straight, strike_high | 527/1000 | 0.496-0.558 | 473 | 0 |
| free:strike_flank+strike_high+strike_straight | strike_flank, strike_high, strike_straight | 522/1000 | 0.491-0.553 | 478 | 0 |
| free:strike_high+strike_straight+strike_straight | strike_high, strike_straight, strike_straight | 519/1000 | 0.488-0.550 | 481 | 0 |
| free:strike_straight+strike_flank+strike_high | strike_straight, strike_flank, strike_high | 518/1000 | 0.487-0.549 | 482 | 0 |
| free:strike_flank+strike_straight+strike_high | strike_flank, strike_straight, strike_high | 516/1000 | 0.485-0.547 | 484 | 0 |
| free:strike_straight+strike_flank+strike_flank | strike_straight, strike_flank, strike_flank | 511/1000 | 0.480-0.542 | 489 | 0 |
| free:strike_flank+strike_straight+strike_flank | strike_flank, strike_straight, strike_flank | 510/1000 | 0.479-0.541 | 490 | 0 |
| free:strike_straight+strike_straight+strike_high | strike_straight, strike_straight, strike_high | 508/1000 | 0.477-0.539 | 492 | 0 |
| free:strike_straight+strike_high+strike_straight | strike_straight, strike_high, strike_straight | 506/1000 | 0.475-0.537 | 494 | 0 |
| free:strike_flank+strike_flank+strike_straight | strike_flank, strike_flank, strike_straight | 495/1000 | 0.464-0.526 | 505 | 0 |
| free:strike_straight+strike_straight+strike_flank | strike_straight, strike_straight, strike_flank | 485/1000 | 0.454-0.516 | 515 | 0 |
| team:strike_sacrifice | strike_sacrifice, strike_sacrifice, strike_sacrifice | 475/1000 | 0.444-0.506 | 525 | 0 |
| free:strike_flank+strike_straight+strike_straight | strike_flank, strike_straight, strike_straight | 475/1000 | 0.444-0.506 | 525 | 0 |
| free:strike_straight+strike_flank+strike_straight | strike_straight, strike_flank, strike_straight | 471/1000 | 0.440-0.502 | 529 | 0 |
| free:strike_straight+strike_straight+strike_straight | strike_straight, strike_straight, strike_straight | 466/1000 | 0.435-0.497 | 534 | 0 |
| team:strike_converge | strike_converge, strike_converge, strike_converge | 14/1000 | 0.008-0.023 | 986 | 0 |

Controls: ctl_one_script_choices_are_reference PASS; ctl_choice_log_is_the_fixed_choice PASS; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS

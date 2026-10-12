
# Explosive Dash

## Platformer

The primary goal of the game is to make it to the end as fast as possible using **phase dashes** and **rocket jumps** to make it past obstacles.  

You lose if you hit too many obstacles (depends on the level difficulty)

Going to the sides is controlled by A and D, jumping uses the Spacebar, phase dashing uses Shift and launching a rocket uses X.

**Game loop:** Check if the player has entered a movement control -> Check if an obstacle has been hit or if an ability has been used -> Redraw the frame -> Short wait

**Phase dashes** - Dashes that allow you to go through or "phase" through a limited distance, usually used to get through obstacles or walls.

**Rocket jumps** - Explosions that require timing for maximal distance, used to speed up level completion and get over certain gaps.

There are 3 distinct levels, each one increasing in length and obstacles. Level 1 is relatively short while levels 2 and 3 are already a more substantial increase in length.

Time is saved at the end of the level, putting the shortest time at the top of the leaderboard.

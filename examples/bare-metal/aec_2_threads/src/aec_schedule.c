#include "aec_schedule.h"

/* Structure used for issuing jobs on cores */
schedule_t sch = {
{
  {{0, 0, 1},{2, 0, 1},{1, 1, 1},},
  {{1, 0, 1},{0, 1, 1},{2, 1, 1},},
},
{
  {{0, 0, 1},{0, 1, 1},},
  {{1, 0, 1},{1, 1, 1},},
},
{
  {{0, 0, 1},},
  {{0, 1, 1},},
},
{
  {{0, 1},},
  {{1, 1},},
},
{
  {{0, 1},{2, 1},},
  {{1, 1},{0, 0},},
},
};

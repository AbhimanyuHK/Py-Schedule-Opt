import math
import os
import calendar

import pandas as pd
from pyomo.environ import *
from pyomo.opt import SolverFactory

"""
Example:

threshold: 5
multiplier: 2
wage: 10,
shift duration: 8

cost = 5 * 10 + (8 - 5) * 10 * 2 = 110

worker: 3
day: 1
shift: 3

cost: 1 * 3 * 3

"""

os.environ["NEOS_EMAIL"] = "manyu19940@hotmail.com"

lp_df = pd.read_excel("LP Sched Data.xlsx")
lp_df["Full Name"] = lp_df["Last Name"] + " " + lp_df["First Name"]

year, month = 2023, 8
weekend_list = ["friday", "saturday", "sunday"]
# Define days (1 week)
# days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
cal = calendar.Calendar()
days = {str(x): calendar.day_name[x.weekday()] for x in cal.itermonthdates(year, month) if x.month == month}

sun_day_count = [d for d in days if days[d].lower() == "sunday"]
sat_day_count = [d for d in days if days[d].lower() == "saturday"]
fri_day_count = [d for d in days if days[d].lower() == "friday"]

weekend_max_count = max([len(sun_day_count), len(sat_day_count), len(fri_day_count)])


# Enter shifts of each day
AM_SHIFT = "morning"
PM_SHIFT = "evening"
NIGHT_SHIFT = "night"
shifts = [AM_SHIFT, PM_SHIFT, NIGHT_SHIFT]  # 3 shifts of 8 hours
days_shifts = {day: shifts for day in days}  # dict with day as key and list of its shifts as value

# Enter workers ids (name, number, ...)
# workers = ['W' + str(i) for i in range(1, 11)]  # 10 workers available, more than needed
workers = list(lp_df["Full Name"])

locations = list(lp_df.columns)[19:-1]
print(locations)

# days = [f"D_{x}" for x in range(1, 2)]
# shifts = ['morning', 'evening', 'night']  # 3 shifts of 8 hours
# days_shifts = {day: shifts for day in days}  # dict with day as key and list of its shifts as value
# workers = list(lp_df["Full Name"])[:1]
# locations = ["Defiance Percent"]
# # print(locations)


shift_hour = 9

# Initialize model
model = ConcreteModel()

# binary variables representing if a worker is scheduled somewhere
model.works = Var(
    ((
        worker, day, shift, location
    ) for worker in workers for day in days for shift in days_shifts[day] for location in locations),
    within=Binary,
    initialize=0
)

# binary variables representing if a worker is necessary
model.needed = Var(workers, within=Binary, initialize=0)

# binary variables representing if a worker worked on sunday but not on saturday (avoid if possible)
model.no_pref = Var(workers, within=Binary, initialize=0)


# Define an objective function with model as input, to pass later
def obj_rule(m):
    return sum(
        m.works[
            worker, day, shift, location
        ] for worker in workers for day in days for shift in days_shifts[day] for location in locations
    )
    # return sum(m.no_pref[worker] for worker in workers) + sum(c * m.needed[worker] for worker in workers) + 1


# we multiply the second term by a constant to make sure that it is the primary objective
# since sum(m.no_prefer) is at most len(workers), len(workers) + 1 is a valid constant.


# add objective function to the model. rule (pass function) or expr (pass expression directly)
model.obj = Objective(rule=obj_rule, sense=minimize)

model.constraints = ConstraintList()  # Create a set of constraints

records = lp_df.to_dict(orient="records")

# MIN / MAX shifts
for record in records:
    # print(record)
    # print(record["Full Name"])
    current_worker = record["Full Name"]

    if not (current_worker in workers):
        continue

    # 1 work N-day N-shift N-Location => Max Shifts
    model.constraints.add(
        sum(
            model.works[
                current_worker, day, shift, location
            ] for day in days_shifts for shift in days_shifts[day] for location in locations
        ) <= record['Max Shifts']
    )
    # 1 work N-day N-shift N-Location => Min Shifts
    model.constraints.add(
        sum(
            model.works[
                current_worker, day, shift, location
            ] for day in days_shifts for shift in days_shifts[day] for location in locations
        ) >= record['Min Shifts']
    )

# MIN / MAX shifts for Weekends
for record in records:
    current_worker = record["Full Name"]

    if not (current_worker in workers):
        continue

    # 1 work N-day N-shift N-Location => Block Weekends (Fri, Sat, Sun)
    # model.constraints.add(
    #     sum(
    #         model.works[
    #             current_worker, day, shift, location
    #         ] for day in days_shifts for shift in days_shifts[day] for location in locations
    #         if days[day].lower() in weekend_list
    #     ) <= record['Block Weekends (Fri, Sat, Sun)'] * weekend_max_count
    # )

    for weekend_days_x in zip(fri_day_count, sat_day_count, sun_day_count):
        model.constraints.add(
            sum(
                model.works[
                    current_worker, day, shift, location
                ] for day in weekend_days_x for shift in days_shifts[day] for location in locations
                if days[day].lower() in weekend_list
            ) <= 1
        )

    if record["Full Time"]:
        job_type_count = 7
    elif record["Part Time"]:
        job_type_count = 3
    elif record["Per Diem"]:
        job_type_count = 0
    else:
        job_type_count = record['Block Weekends (Fri, Sat, Sun)'] * weekend_max_count

    model.constraints.add(
        sum(
            model.works[
                current_worker, day, shift, location
            ] for day in days_shifts for shift in days_shifts[day] for location in locations
            if days[day].lower() in weekend_list
        ) <= job_type_count
    )

# AM/PM MAX shifts
for record in records:
    current_worker = record["Full Name"]

    if not (current_worker in workers):
        continue

    model.constraints.add(
        sum(
            model.works[
                current_worker, day, shift, location
            ] for day in days_shifts for shift in days_shifts[day] for location in locations
            if shift == AM_SHIFT
        ) <= math.floor(record['AM Shift Percent'] * record['Max Shifts'] + 1)
    )

    model.constraints.add(
        sum(
            model.works[
                current_worker, day, shift, location
            ] for day in days_shifts for shift in days_shifts[day] for location in locations
            if shift == PM_SHIFT
        ) <= math.floor(record['PM Shift Percent'] * record['Max Shifts'] + 1)
    )

# MIN / MAX shifts for Consecutive
for record in records:
    current_worker = record["Full Name"]

    if not (current_worker in workers):
        continue

    model.constraints.add(
        sum(
            model.works[
                current_worker, day1, shift, location
            ] + model.works[
                current_worker, day2, shift, location
            ] for day1, day2 in zip(days_shifts, list(days_shifts.keys())[1:])
            for shift in days_shifts[day1] for location in locations
            if shift == PM_SHIFT
        ) >= record['Min Consecutive PM Shifts']
    )

    model.constraints.add(
        sum(
            model.works[
                current_worker, day1, shift, location
            ] + model.works[
                current_worker, day2, shift, location
            ] for day1, day2 in zip(days_shifts, list(days_shifts.keys())[1:])
            for shift in days_shifts[day1] for location in locations
            if shift == PM_SHIFT
        ) <= record['Max Consecutive PM Shifts']
    )

    model.constraints.add(
        sum(
            model.works[
                current_worker, day1, shift, location
            ] + model.works[
                current_worker, day2, shift, location
            ] for day1, day2 in zip(days_shifts, list(days_shifts.keys())[1:])
            for shift in days_shifts[day1] for location in locations
            if shift == AM_SHIFT
        ) >= record['Min Consecutive AM Shifts']
    )

    model.constraints.add(
        sum(
            model.works[
                current_worker, day1, shift, location
            ] + model.works[
                current_worker, day2, shift, location
            ] for day1, day2 in zip(days_shifts, list(days_shifts.keys())[1:])
            for shift in days_shifts[day1] for location in locations
            if shift == AM_SHIFT
        ) <= record['Max Consecutive AM Shifts']
    )

# N-Location 1 day 1 shift = 1 worker ( now max 3)
for location in locations:
    for day, shifts in days_shifts.items():
        for shift in shifts:
            model.constraints.add(
                sum(
                    model.works[worker, day, shift, location] for worker in workers
                ) >= 0
            )
            model.constraints.add(
                sum(
                    model.works[worker, day, shift, location] for worker in workers
                ) <= 3
            )

# 1 Worker 1 location availability for N-day N-Shift
for record in records:
    current_worker = record["Full Name"]
    if not (current_worker in workers):
        continue

    for location in locations:
        if not (location in record):
            continue

        model.constraints.add(
            sum(
                model.works[current_worker, day, shift, location] for day in days for shift in days_shifts[day]
                # ) >= math.floor(record[location] * record['Min Shifts'])
            ) >= 0
        )
        model.constraints.add(
            sum(
                model.works[current_worker, day, shift, location] for day in days for shift in days_shifts[day]
            ) <= math.floor(record[location] * record['Max Shifts'] + 1)
        )

# MIN / MAX shift Hours
for record in records:
    current_worker = record["Full Name"]

    if not (current_worker in workers):
        continue

    # 1 work N-day N-shift N-Location => Max Shifts
    model.constraints.add(
        sum(
            shift_hour * model.works[
                current_worker, day, shift, location
            ] for day in days_shifts for shift in days_shifts[day] for location in locations
        ) <= int(record['Max Hours'])
    )
    # 1 work N-day N-shift N-Location => Min Shifts
    model.constraints.add(
        sum(
            shift_hour * model.works[
                current_worker, day, shift, location
            ] for day in days_shifts for shift in days_shifts[day] for location in locations
            # ) >= int(record['Min Hours']) - shift_hour
        ) >= 0
    )

# 1 worker 1 shift for 1 Day
for record in records:
    current_worker = record["Full Name"]

    if not (current_worker in workers):
        continue

    for day in days_shifts:
        model.constraints.add(
            sum(
                model.works[
                    current_worker, day, shift, location
                ] for shift in days_shifts[day] for location in locations
            ) <= 1
        )
        model.constraints.add(
            sum(
                model.works[
                    current_worker, day, shift, location
                ] for shift in days_shifts[day] for location in locations
            ) >= 0
        )

# model.write("test.dat", format="dat")
# model.pprint()
model.pprint(ostream=open("test.txt", "w"))
# # model.pprint()
# # cbc_path = "C://Users//manyu//Downloads//Cbc-2.10.4-x86_64-w64-mingw32//bin//cbc.exe"
# # opt = SolverFactory(cbc_path)  # choose a solver
# # results = opt.solve(model)  # solve the model with the selected solver
#

opt = SolverFactory('cbc')  # Select solver
solver_manager = SolverManagerFactory('neos')  # Solve in neos server
results = solver_manager.solve(model, opt=opt)


def get_workers_needed(needed):
    """Extract to a list the needed workers for the optimal solution."""
    workers_needed = []
    for worker in workers:
        if needed[worker].value == 1:
            workers_needed.append(worker)
    return workers_needed


def get_work_table(works):
    """Build a timetable of the week as a dictionary from the model's optimal solution."""
    week_table = {location: {day: {shift: [] for shift in days_shifts[day]} for day in days} for location in locations}
    df_json = []
    for worker in workers:
        for location in locations:
            for day in days:
                for shift in days_shifts[day]:
                    if works[worker, day, shift, location].value == 1:
                        week_table[location][day][shift].append(worker)
                        df_json.append({
                            "location": location,
                            "day": day,
                            "weekday": days[day],
                            "shift": shift,
                            "worker": worker
                        })
    return df_json


def get_no_preference(no_pref):
    """Extract to a list the workers not satisfied with their weekend preference."""
    return [worker for worker in workers if no_pref[worker].value == 1]


workers_needed = get_workers_needed(model.needed)  # dict with the optimal timetable
week_table = get_work_table(model.works)  # list with the required workers
workers_no_pref = get_no_preference(model.no_pref)  # list with the non-satisfied workers (work on Sat but not on Sun)

print(workers_needed)
print()
print(week_table)
print()
print(workers_no_pref)
print()
print(results)
print()
# model.works.display()

result_df = pd.DataFrame(week_table)
print(result_df)

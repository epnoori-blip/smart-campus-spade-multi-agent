"""
Smart Campus Space Coordination System
Multi-Agent System using SPADE 4.x (Python)

Agents  : LecturerAgent, SchedulerAgent
Scenarios:
  1 - Lecture room booking (success)
  2 - Seminar space reservation (success)
  3 - Conflict resolution (lecturer wins over student)
"""

import asyncio
import spade
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message
from spade.template import Template

# ─────────────────────────────────────────
# Simulated environment (shared room DB)
# ─────────────────────────────────────────
ROOMS = {
    "R101": {
        "type": "lecture_hall",
        "capacity": 80,
        "equipment": ["projector", "whiteboard"],
        "status": "available",
        "booked_by": None,
        "booked_priority": 0,
    },
    "R202": {
        "type": "seminar",
        "capacity": 30,
        "equipment": ["whiteboard"],
        "status": "available",
        "booked_by": None,
        "booked_priority": 0,
    },
}

def find_room(min_capacity, need_projector):
    for rid, info in ROOMS.items():
        if info["status"] != "available":
            continue
        if info["capacity"] < min_capacity:
            continue
        if need_projector and "projector" not in info["equipment"]:
            continue
        return rid
    return None

def find_any_room(min_capacity, need_projector):
    for rid, info in ROOMS.items():
        if info["capacity"] < min_capacity:
            continue
        if need_projector and "projector" not in info["equipment"]:
            continue
        return rid
    return None

def book_room(room_id, requester, priority=1):
    ROOMS[room_id]["status"] = "booked"
    ROOMS[room_id]["booked_by"] = requester
    ROOMS[room_id]["booked_priority"] = priority

def release_room(room_id):
    ROOMS[room_id]["status"] = "available"
    ROOMS[room_id]["booked_by"] = None
    ROOMS[room_id]["booked_priority"] = 0


# ════════════════════════════════════════
# SCHEDULER AGENT
# ════════════════════════════════════════
class SchedulerAgent(Agent):

    class HandleRequests(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=30)
            if not msg:
                return

            perf   = msg.get_metadata("performative") or ""
            sender = str(msg.sender).split("/")[0]
            body   = msg.body or ""
            thread = msg.thread or ""

            print(f"\n[SchedulerAgent] Received {perf.upper()} from {sender} [thread={thread}]")
            print(f"                Content: {body}")

            if perf == "request":
                parts     = dict(p.split("=") for p in body.split("|"))
                requester = parts.get("requester", sender)
                purpose   = parts.get("purpose", "meeting")
                min_cap   = int(parts.get("min_capacity", 10))
                need_proj = parts.get("need_projector", "false") == "true"
                priority  = int(parts.get("priority", 1))

                room_id = find_room(min_cap, need_proj)

                if room_id:
                    book_room(room_id, requester, priority)
                    reply = Message(to=sender, thread=thread)
                    reply.set_metadata("performative", "inform")
                    reply.body = (
                        f"room={room_id}|status=confirmed|"
                        f"capacity={ROOMS[room_id]['capacity']}|purpose={purpose}"
                    )
                    await self.send(reply)
                    print(f"[SchedulerAgent] Sent INFORM -> room {room_id} confirmed for {requester}")

                else:
                    target = find_any_room(min_cap, need_proj)
                    if target:
                        existing_booker   = ROOMS[target]["booked_by"]
                        existing_priority = ROOMS[target]["booked_priority"]

                        if priority > existing_priority:
                            print(f"\n[SchedulerAgent] *** CONFLICT DETECTED! ***")
                            print(f"                {requester} (priority={priority}) displaces")
                            print(f"                {existing_booker} (priority={existing_priority})")
                            release_room(target)
                            book_room(target, requester, priority)

                            reply = Message(to=sender, thread=thread)
                            reply.set_metadata("performative", "inform")
                            reply.body = (
                                f"room={target}|status=confirmed_after_conflict|"
                                f"capacity={ROOMS[target]['capacity']}|"
                                f"displaced={existing_booker}|purpose={purpose}"
                            )
                            await self.send(reply)
                            print(f"[SchedulerAgent] Sent INFORM (conflict resolved) -> {target} to {requester}")
                        else:
                            reply = Message(to=sender, thread=thread)
                            reply.set_metadata("performative", "failure")
                            reply.body = f"reason=lower_priority|existing_booker={existing_booker}"
                            await self.send(reply)
                            print(f"[SchedulerAgent] Sent FAILURE -> lower priority")
                    else:
                        reply = Message(to=sender, thread=thread)
                        reply.set_metadata("performative", "failure")
                        reply.body = "reason=no_room_available"
                        await self.send(reply)
                        print(f"[SchedulerAgent] Sent FAILURE -> no room available")

    async def setup(self):
        print("[SchedulerAgent] Agent started.")
        self.add_behaviour(self.HandleRequests())


# ════════════════════════════════════════
# LECTURER AGENT — one behaviour per scenario
# each filtered by thread
# ════════════════════════════════════════
class LecturerAgent(Agent):

    # ── Scenario 1 ──────────────────────
    class Scenario1(OneShotBehaviour):
        async def run(self):
            await asyncio.sleep(1)
            print("\n" + "="*55)
            print("  SCENARIO 1: Lecture Room Booking")
            print("="*55)

            msg = Message(to="scheduler@localhost", thread="sc1")
            msg.set_metadata("performative", "request")
            msg.body = (
                "requester=lecturer@localhost|purpose=lecture|"
                "min_capacity=60|need_projector=true|priority=3"
            )
            await self.send(msg)
            print("[LecturerAgent] Sent REQUEST: lecture hall, 60+ seats, projector needed")

            reply = await self.receive(timeout=10)
            if reply:
                perf  = reply.get_metadata("performative")
                print(f"[LecturerAgent] Received {perf.upper()}: {reply.body}")
                if perf == "inform":
                    parts = dict(p.split("=") for p in reply.body.split("|"))
                    print(f"[LecturerAgent] DECISION: Room {parts['room']} confirmed. Lecture proceeds.")
                else:
                    print("[LecturerAgent] DECISION: No room available. Will reschedule.")

    # ── Scenario 2 ──────────────────────
    class Scenario2(OneShotBehaviour):
        async def run(self):
            await asyncio.sleep(6)
            print("\n" + "="*55)
            print("  SCENARIO 2: Seminar Space Reservation")
            print("="*55)

            msg = Message(to="scheduler@localhost", thread="sc2")
            msg.set_metadata("performative", "request")
            msg.body = (
                "requester=lecturer@localhost|purpose=seminar|"
                "min_capacity=20|need_projector=false|priority=2"
            )
            await self.send(msg)
            print("[LecturerAgent] Sent REQUEST: seminar room, 20+ seats")

            reply = await self.receive(timeout=10)
            if reply:
                perf  = reply.get_metadata("performative")
                print(f"[LecturerAgent] Received {perf.upper()}: {reply.body}")
                if perf == "inform":
                    parts = dict(p.split("=") for p in reply.body.split("|"))
                    print(f"[LecturerAgent] DECISION: Room {parts['room']} reserved. Seminar ready.")
                else:
                    print("[LecturerAgent] DECISION: No seminar room found.")

    # ── Scenario 3 ──────────────────────
    class Scenario3(OneShotBehaviour):
        async def run(self):
            await asyncio.sleep(11)
            print("\n" + "="*55)
            print("  SCENARIO 3: Conflict Resolution")
            print("="*55)

            # Reset R101 and simulate student low-priority booking
            release_room("R101")
            print("[System] Simulating: student_group booked R101 (priority=1)")
            book_room("R101", "student_group@localhost", priority=1)
            print(f"[System] R101 status: {ROOMS['R101']['status']} | by: {ROOMS['R101']['booked_by']}")

            msg = Message(to="scheduler@localhost", thread="sc3")
            msg.set_metadata("performative", "request")
            msg.body = (
                "requester=lecturer@localhost|purpose=urgent_lecture|"
                "min_capacity=60|need_projector=true|priority=3"
            )
            await self.send(msg)
            print("[LecturerAgent] Sent REQUEST: urgent lecture, priority=3 (HIGH)")

            reply = await self.receive(timeout=10)
            if reply:
                perf  = reply.get_metadata("performative")
                print(f"[LecturerAgent] Received {perf.upper()}: {reply.body}")
                if perf == "inform":
                    parts = dict(p.split("=") for p in reply.body.split("|"))
                    print(f"[LecturerAgent] DECISION: Conflict resolved. Room {parts['room']} assigned.")
                    print(f"                Urgent lecture can proceed.")
                else:
                    print("[LecturerAgent] DECISION: Could not get room. Checking alternatives.")

    async def setup(self):
        print("[LecturerAgent] Agent started.")

        # Each behaviour filtered to only receive messages with its own thread
        t1 = Template(); t1.thread = "sc1"
        t2 = Template(); t2.thread = "sc2"
        t3 = Template(); t3.thread = "sc3"

        self.add_behaviour(self.Scenario1(), t1)
        self.add_behaviour(self.Scenario2(), t2)
        self.add_behaviour(self.Scenario3(), t3)


# ════════════════════════════════════════
# MAIN
# ════════════════════════════════════════
async def main():
    print("="*55)
    print("  Smart Campus Space Coordination System")
    print("  SPADE Multi-Agent System")
    print("="*55)

    scheduler = SchedulerAgent("scheduler@localhost", "scheduler_pass")
    lecturer  = LecturerAgent("lecturer@localhost",  "lecturer_pass")

    await scheduler.start(auto_register=True)
    await lecturer.start(auto_register=True)

    print("\n[System] Both agents running. Executing scenarios...\n")
    await asyncio.sleep(25)

    print("\n" + "="*55)
    print("  Final Room Status:")
    for rid, info in ROOMS.items():
        print(f"  {rid}: {info['status']} | booked_by: {info['booked_by']}")
    print("="*55)

    await lecturer.stop()
    await scheduler.stop()
    print("\n[System] Simulation complete.")

if __name__ == "__main__":
    spade.run(main())

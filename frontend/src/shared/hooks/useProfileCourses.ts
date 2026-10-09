import { useMemo } from 'react';
import { useProfile } from './useProfile';
import { sameBranchFamily, splitCourseCodes, toMinutes } from '../lib/normalise';
import type { TimetableSlot } from '../types/api';

interface ProfileCourseResult {
  /** Row id from the timetable slot; kept through the split and filter. */
  id: number;
  day: string;
  start_time: string;
  end_time: string;
  room: string;
  course_code: string;
  branch_or_program: string;
  semester: number;
  is_opted_in: boolean;
  sort_key: number;
  [key: string]: unknown;
}

/**
 * The student's own timetable, filtered by their profile.
 *
 * The uploaded master timetable lists every branch, so it has to be narrowed
 * before anything is shown: a CSE A student must not see an ECE paper. The
 * rules, in order:
 *
 * 1. the slot's semester must match the profile's
 * 2. a course shows regardless of branch if it is in the profile - an elected
 *    elective, or an extra / backlog course
 * 3. otherwise the slot's branch must belong to the student's branch family
 *
 * An open elective is *not* enough on its own to earn a place here. The master
 * grid lists every elective the college offers, to every branch, so showing them
 * all added 71 rows of courses nobody had chosen - more than half the timetable -
 * and made the filter look broken. An elective appears when the student has
 * actually opted into it, which is what makes it theirs.
 *
 * Duplicates are then dropped, because one class can legitimately arrive twice
 * from two sections sharing a room or a re-uploaded timetable.
 */
export default function useProfileCourses(
  slots: TimetableSlot[] | undefined,
  options: { includeOtherSemesters?: boolean } = {}
): ProfileCourseResult[] {
  const { branch, semester, optedInCodes } = useProfile();
  const { includeOtherSemesters = false } = options;

  const optedIn = useMemo(() => new Set(optedInCodes), [optedInCodes]);

  return useMemo(() => {
    const rows = (slots || []).flatMap(slot =>
      // A cell listing two papers ("OE3M27/ME5D02") is two courses.
      splitCourseCodes(slot.course_code).map(code => ({ ...slot, course_code: code }))
    );

    const seen = new Set<string>();
    const relevant: ProfileCourseResult[] = [];

    rows.forEach(slot => {
      const code = slot.course_code.toUpperCase();
      // Only what the profile claims. An elective nobody chose is not theirs.
      const inProfile = optedIn.has(code);

      if (!includeOtherSemesters && semester && slot.semester && slot.semester !== semester) {
        if (!inProfile) return;
      }

      const slotBranch = slot.branch_or_program;
      const branchOk = !slotBranch || sameBranchFamily(slotBranch, branch);
      if (!inProfile && !branchOk) return;

      // De-duplicate on when/where/what, not the row id.
      const key = [slot.day, slot.start_time, slot.end_time, slot.room, code].join('|');
      if (seen.has(key)) return;
      seen.add(key);

      relevant.push({
        ...slot,
        course_code: code,
        is_opted_in: inProfile,
        sort_key: toMinutes(slot.start_time),
      });
    });

    return relevant;
  }, [slots, branch, semester, optedIn, includeOtherSemesters]);
}

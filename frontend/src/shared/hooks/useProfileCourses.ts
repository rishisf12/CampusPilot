import { useMemo } from 'react';
import { useProfile } from './useProfile';
import {
  branchFamily,
  branchesInText,
  courseBelongsToBranch,
  isOpenElective,
  isPostgradCourse,
  splitCourseCodes,
  toMinutes,
} from '../lib/normalise';
import type { TimetableSlot } from '../types/api';

/**
 * Check if a branch string has a specific section (e.g., "CSE-A", "CSE-B", "DS-E1")
 * Returns the specific section if found, otherwise undefined.
 */
function getSpecificSection(branch: string): string | undefined {
  if (!branch) return undefined;
  // Match patterns like "CSE-A", "CSE-B", "DS-E1", "DS-E2", etc.
  // Pattern: branch code + space/hyphen + section letter/number
  const match = branch.match(/^([A-Z]{2,4})[\s-]+([A-Z]\d?)$/i);
  if (match) {
    return match[0].toUpperCase().replace(/\s+/g, '-');
  }
  return undefined;
}

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
  const { branch, semester, optedInCodes, programme } = useProfile();
  const { includeOtherSemesters = false } = options;

  const optedIn = useMemo(() => new Set(optedInCodes), [optedInCodes]);

  return useMemo(() => {
    const rows = (slots || []).flatMap(slot =>
      // A cell listing two papers ("OE3M27/ME5D02") is two courses.
      splitCourseCodes(slot.course_code).map(code => ({ ...slot, course_code: code }))
    );

    const seen = new Set<string>();
    const relevant: ProfileCourseResult[] = [];

    const isPostgradProgramme = ['MTECH', 'ME', 'MDES', 'PHD'].includes(
      (programme || '').toUpperCase()
    );

    rows.forEach(slot => {
      const code = slot.course_code.toUpperCase();
      // Only what the profile claims. An elective nobody chose is not theirs.
      const inProfile = optedIn.has(code);

      // Skip postgraduate courses for undergraduate programmes
      if (isPostgradCourse(code) && !isPostgradProgramme) return;

      // Coerce both to number to avoid string/number mismatch from API
      const slotSem = Number(slot.semester);
      const profileSem = Number(semester);
      if (!includeOtherSemesters && profileSem && slotSem && slotSem !== profileSem) {
        if (!inProfile) return;
      }

      const slotBranch = slot.branch_or_program;

      // Check if this is a shared cell (multiple branches)
      const branchFamilies = branchesInText(slotBranch);
      const studentFamily = branchFamily(branch);

      let branchOk = false;
      if (isOpenElective(code)) {
        // Electives are NOT branch-specific — show only if student opted in
        branchOk = inProfile;
      } else if (studentFamily) {
        // Core course: check if course prefix matches student's branch family
        const courseMatchesFamily = courseBelongsToBranch(code, branch);

        // Also check if the slot's specific section matches student's specific section
        const slotBranch = slot.branch_or_program;
        const studentBranch = branch;

        // Check for specific sections directly in the branch strings
        const slotSpecificSection = getSpecificSection(slotBranch);
        const studentSpecificSection = getSpecificSection(studentBranch);

        if (slotSpecificSection && studentSpecificSection) {
          // Both have specific sections - must match exactly
          branchOk = slotSpecificSection === studentSpecificSection;
        } else if (slotSpecificSection && !studentSpecificSection) {
          // Slot has specific section but student doesn't - show only if student's family matches
          const slotFamily = branchFamily(slotBranch);
          branchOk = slotFamily === branchFamily(studentBranch);
        } else if (!slotSpecificSection && studentSpecificSection) {
          // Student has specific section but slot doesn't - show if generic branch matches
          const slotFamily = branchFamily(slotBranch);
          branchOk = slotFamily === branchFamily(studentBranch);
        } else {
          // Neither has specific section - fall back to course family match
          branchOk = courseMatchesFamily;
        }
      } else {
        // No student family (shouldn't happen for signed-up users): fall back to slot branch
        branchOk = !slotBranch || branchFamilies.includes(studentFamily);
      }

      if (!branchOk) return;

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
  }, [slots, branch, semester, programme, optedIn, includeOtherSemesters]);
}

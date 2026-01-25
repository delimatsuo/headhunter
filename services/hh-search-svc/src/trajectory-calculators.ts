/**
 * Trajectory Calculators for Phase 8: Career Trajectory Analysis
 *
 * This module implements trajectory direction classification that analyzes
 * title sequences to determine career movement patterns (upward, lateral, downward).
 *
 * Functions:
 * - calculateTrajectoryDirection: Classifies career direction from title sequence
 * - mapTitleToLevel: Maps job titles to normalized level indices
 *
 * All functions handle edge cases (empty, unknown titles) by returning neutral values.
 */

// ============================================================================
// Constants
// ============================================================================

/**
 * Extended level ordering that separates technical and management tracks.
 * Technical track: intern -> junior -> mid -> senior -> staff -> principal -> distinguished
 * Management track: manager -> senior_manager -> director -> senior_director -> vp -> svp -> c-level
 */
export const LEVEL_ORDER_EXTENDED = [
  'intern', 'junior', 'mid', 'senior', 'staff', 'principal', 'distinguished',
  'manager', 'senior_manager', 'director', 'senior_director', 'vp', 'svp', 'c-level'
];

/**
 * Level index mapping for quick lookups.
 * Technical levels: 0-6, Management levels: 7-13
 */
const LEVEL_INDEX: Record<string, number> = {
  // Technical track
  'intern': 0, 'junior': 1, 'entry': 1, 'associate': 1,
  'mid': 2, 'intermediate': 2,
  'senior': 3, 'sr': 3,
  'staff': 4, 'lead': 4,
  'principal': 5,
  'distinguished': 6, 'fellow': 6,
  // Management track (offset by 7 to indicate different track)
  'manager': 7, 'engineering manager': 7, 'em': 7,
  'senior_manager': 8, 'senior manager': 8,
  'director': 9,
  'senior_director': 10, 'senior director': 10,
  'vp': 11, 'vice president': 11,
  'svp': 12, 'senior vice president': 12,
  'c-level': 13, 'cto': 13, 'ceo': 13, 'coo': 13, 'cfo': 13
};

const TECHNICAL_MAX_INDEX = 6;
const MANAGEMENT_MIN_INDEX = 7;

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Trajectory direction indicating career movement over time.
 */
export type TrajectoryDirection = 'upward' | 'lateral' | 'downward';

// ============================================================================
// Title Mapping Functions
// ============================================================================

/**
 * Maps a job title to a normalized level index.
 * Returns -1 if the title cannot be mapped.
 *
 * @param title - Job title to map
 * @returns Level index (0-13) or -1 if unknown
 */
export function mapTitleToLevel(title: string): number {
  if (!title || typeof title !== 'string') return -1;

  const normalized = title.toLowerCase().trim();

  // Direct lookup
  if (LEVEL_INDEX[normalized] !== undefined) {
    return LEVEL_INDEX[normalized];
  }

  // Pattern matching for common variations
  const patterns: [RegExp, number][] = [
    [/\b(intern|internship)\b/i, 0],
    [/\b(junior|jr|entry|associate)\b/i, 1],
    [/\b(mid[-\s]?level|intermediate)\b/i, 2],
    [/\b(senior|sr)\s+(engineer|developer|architect)/i, 3],
    [/\b(staff|lead)\s+(engineer|developer)/i, 4],
    [/\b(principal|lead)\s+architect/i, 5],
    [/\b(distinguished|fellow)\b/i, 6],
    [/\bengineering\s+manager\b/i, 7],
    [/\bmanager\b/i, 7],
    [/\bsenior\s+manager\b/i, 8],
    [/\bdirector\b/i, 9],
    [/\bsenior\s+director\b/i, 10],
    [/\b(vp|vice\s+president)\b/i, 11],
    [/\b(svp|senior\s+vice\s+president)\b/i, 12],
    [/\b(cto|ceo|coo|cfo|chief)\b/i, 13]
  ];

  for (const [pattern, index] of patterns) {
    if (pattern.test(normalized)) {
      return index;
    }
  }

  // Fallback: check if title contains level keywords
  if (/senior/i.test(normalized)) return 3;
  if (/junior/i.test(normalized) || /jr\b/i.test(normalized)) return 1;

  return -1; // Unknown level
}

// ============================================================================
// Direction Classification
// ============================================================================

/**
 * Calculates career direction from a sequence of job titles.
 *
 * Rules:
 * - Upward: Average delta > 0.5 (mostly promotions)
 * - Lateral: Average delta between -0.5 and 0.5 (same-level moves)
 * - Downward: Average delta < -0.5 (mostly demotions/resets)
 *
 * Track changes (tech -> management) are normalized to relative positions
 * to avoid false positives. For example, Senior Engineer (3) -> Engineering
 * Manager (7) is considered lateral since both are mid-career positions.
 *
 * @param titleSequence - Array of job titles in chronological order (oldest first)
 * @returns Direction classification
 */
export function calculateTrajectoryDirection(
  titleSequence: string[]
): TrajectoryDirection {
  if (!titleSequence || titleSequence.length < 2) {
    return 'lateral'; // Neutral when insufficient data
  }

  // Map titles to level indices
  const levels = titleSequence.map(mapTitleToLevel);

  // Filter out unknown levels (-1)
  const validLevels = levels.filter(l => l !== -1);
  if (validLevels.length < 2) {
    return 'lateral'; // Neutral when insufficient valid levels
  }

  // Calculate deltas between consecutive valid levels
  // Note: We consider track changes (tech -> mgmt) as lateral unless there's clear level change
  const deltas: number[] = [];
  for (let i = 1; i < validLevels.length; i++) {
    const current = validLevels[i];
    const previous = validLevels[i - 1];

    // Handle track changes (tech -> mgmt or mgmt -> tech)
    const prevIsTech = previous <= TECHNICAL_MAX_INDEX;
    const currIsTech = current <= TECHNICAL_MAX_INDEX;

    if (prevIsTech !== currIsTech) {
      // Track change: compare relative positions within each track
      // Tech senior (3) -> Manager (7) is roughly lateral (both are mid-career)
      // Map to relative position: tech 0-6 maps to mgmt 7-13
      const prevRelative = prevIsTech ? previous : previous - MANAGEMENT_MIN_INDEX;
      const currRelative = currIsTech ? current : current - MANAGEMENT_MIN_INDEX;
      deltas.push(currRelative - prevRelative);
    } else {
      deltas.push(current - previous);
    }
  }

  if (deltas.length === 0) {
    return 'lateral';
  }

  const averageDelta = deltas.reduce((sum, d) => sum + d, 0) / deltas.length;

  if (averageDelta > 0.5) return 'upward';
  if (averageDelta < -0.5) return 'downward';
  return 'lateral';
}

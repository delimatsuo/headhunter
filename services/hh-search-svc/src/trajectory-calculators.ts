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

/**
 * Trajectory velocity indicating speed of career progression.
 */
export type TrajectoryVelocity = 'fast' | 'normal' | 'slow';

/**
 * Trajectory type indicating career track and movement pattern.
 */
export type TrajectoryType = 'technical_growth' | 'leadership_track' | 'lateral_move' | 'career_pivot';

/**
 * Experience entry with title and optional dates.
 */
export interface ExperienceEntry {
  title: string;
  startDate?: string; // ISO date string or null
  endDate?: string;   // ISO date string or null
}

/**
 * Career trajectory data from Together AI enrichment.
 */
export interface CareerTrajectoryData {
  promotion_velocity?: 'fast' | 'normal' | 'slow';
  current_level?: string;
  trajectory_type?: string;
}

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

// ============================================================================
// Velocity Classification
// ============================================================================

/**
 * Calculates trajectory velocity from experience entries with dates.
 * Falls back to Together AI promotion_velocity field when dates unavailable.
 *
 * Rules:
 * - Fast: < 2 years average per level increase
 * - Normal: 2-4 years average per level increase
 * - Slow: > 4 years average per level increase
 *
 * @param experiences - Array of experience entries with titles and dates
 * @param togetherAiData - Optional career trajectory data from Together AI enrichment
 * @returns Velocity classification
 */
export function calculateTrajectoryVelocity(
  experiences: ExperienceEntry[],
  togetherAiData?: CareerTrajectoryData
): TrajectoryVelocity {
  // Try to compute from experience dates
  if (experiences && experiences.length >= 2) {
    const validEntries = experiences.filter(exp =>
      exp.title && exp.startDate && exp.endDate
    );

    if (validEntries.length >= 2) {
      // Map to levels and dates
      const levelsWithDates = validEntries
        .map(exp => ({
          level: mapTitleToLevel(exp.title),
          startDate: new Date(exp.startDate!),
          endDate: new Date(exp.endDate!)
        }))
        .filter(entry => entry.level !== -1)
        .sort((a, b) => a.startDate.getTime() - b.startDate.getTime());

      if (levelsWithDates.length >= 2) {
        // Calculate level increases and time spans
        let totalLevelIncrease = 0;
        let totalYears = 0;

        for (let i = 1; i < levelsWithDates.length; i++) {
          const levelChange = levelsWithDates[i].level - levelsWithDates[i - 1].level;
          if (levelChange > 0) {
            const years = (levelsWithDates[i].startDate.getTime() - levelsWithDates[i - 1].startDate.getTime()) / (1000 * 60 * 60 * 24 * 365);
            totalLevelIncrease += levelChange;
            totalYears += years;
          }
        }

        if (totalLevelIncrease > 0 && totalYears > 0) {
          const yearsPerLevel = totalYears / totalLevelIncrease;

          if (yearsPerLevel < 2) return 'fast';
          if (yearsPerLevel > 4) return 'slow';
          return 'normal';
        }
      }
    }
  }

  // Fallback to Together AI data
  if (togetherAiData?.promotion_velocity) {
    return togetherAiData.promotion_velocity;
  }

  // Default to normal when insufficient data
  return 'normal';
}

// ============================================================================
// Type Classification
// ============================================================================

/**
 * Classifies trajectory type based on title progression and track changes.
 *
 * Rules:
 * - technical_growth: IC progression (Staff, Principal, etc.) without management
 * - leadership_track: Management progression (Manager, Director, VP)
 * - career_pivot: Track changes (IC -> Manager) or function changes
 * - lateral_move: Same-level moves with no clear progression
 *
 * @param titleSequence - Array of job titles in chronological order (oldest first)
 * @returns Trajectory type classification
 */
export function classifyTrajectoryType(
  titleSequence: string[]
): TrajectoryType {
  if (!titleSequence || titleSequence.length < 2) {
    return 'lateral_move'; // Default for insufficient data
  }

  // Map titles to levels
  const levels = titleSequence.map(mapTitleToLevel);
  const validLevels = levels.filter(l => l !== -1);

  if (validLevels.length < 2) {
    return 'lateral_move'; // Default when insufficient valid levels
  }

  // Check for track changes (IC <-> Management)
  let hasTrackChange = false;
  let hasTechnicalGrowth = false;
  let hasLeadershipGrowth = false;

  for (let i = 1; i < validLevels.length; i++) {
    const prev = validLevels[i - 1];
    const curr = validLevels[i];

    const prevIsTech = prev <= TECHNICAL_MAX_INDEX;
    const currIsTech = curr <= TECHNICAL_MAX_INDEX;

    // Detect track changes
    if (prevIsTech !== currIsTech) {
      hasTrackChange = true;
    }

    // Detect growth within tracks
    if (prevIsTech && currIsTech && curr > prev) {
      hasTechnicalGrowth = true;
    }

    if (!prevIsTech && !currIsTech && curr > prev) {
      hasLeadershipGrowth = true;
    }
  }

  // Check for function changes (detected by keyword changes in titles)
  const functionKeywords = titleSequence.map(title => {
    const lower = title.toLowerCase();
    if (/\b(front[-\s]?end|frontend|ui|ux)\b/i.test(lower)) return 'frontend';
    if (/\b(back[-\s]?end|backend|server)\b/i.test(lower)) return 'backend';
    if (/\b(full[-\s]?stack|fullstack)\b/i.test(lower)) return 'fullstack';
    if (/\b(data|analytics|ml|machine learning)\b/i.test(lower)) return 'data';
    if (/\b(devops|sre|infrastructure|platform)\b/i.test(lower)) return 'devops';
    if (/\b(mobile|ios|android)\b/i.test(lower)) return 'mobile';
    if (/\b(security|infosec)\b/i.test(lower)) return 'security';
    return 'general';
  });

  const uniqueFunctions = new Set(functionKeywords.filter(f => f !== 'general'));
  const hasFunctionChange = uniqueFunctions.size > 1;

  // Classification logic
  if (hasTrackChange || hasFunctionChange) {
    return 'career_pivot';
  }

  if (hasTechnicalGrowth) {
    return 'technical_growth';
  }

  if (hasLeadershipGrowth) {
    return 'leadership_track';
  }

  return 'lateral_move';
}

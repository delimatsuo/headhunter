/**
 * Skills Inference - Job Title and Transferable Skills Detection
 *
 * Detects implied skills from job titles and identifies transferable skills
 * with confidence levels for enhanced search matching.
 *
 * Key Features:
 * - Rule-based skill inference from job titles
 * - Transferable skill detection with learning time estimates
 * - Confidence scoring for inferred skills
 *
 * Usage:
 * ```typescript
 * import { inferSkillsFromTitle, findTransferableSkills } from './skills-inference';
 *
 * inferSkillsFromTitle('Senior Full Stack Engineer')
 * // => [{ skill: 'JavaScript', confidence: 0.95, ... }, ...]
 *
 * findTransferableSkills(['Java', 'Spring Boot'])
 * // => [{ fromSkill: 'Java', toSkill: 'Kotlin', transferabilityScore: 0.90, ... }, ...]
 * ```
 */

import { normalizeSkillName } from './skills-service';

// ============================================================================
// TYPES
// ============================================================================

/**
 * A skill inferred from a job title.
 */
export interface InferredSkill {
    /** Canonical skill name */
    skill: string;
    /** Confidence score 0.0-1.0 */
    confidence: number;
    /** Explanation of why this skill was inferred */
    reasoning: string;
    /** Confidence category */
    category: 'highly_probable' | 'probable' | 'likely';
}

/**
 * A skill that can be transferred to from a skill the candidate has.
 */
export interface TransferableSkill {
    /** Skill the candidate currently has */
    fromSkill: string;
    /** Skill they could pivot to */
    toSkill: string;
    /** Transferability score 0.0-1.0 */
    transferabilityScore: number;
    /** Type of skill pivot */
    pivotType: 'same_language_family' | 'same_paradigm' | 'same_domain' | 'complementary';
    /** Estimated time to learn the new skill */
    estimatedLearningTime: 'weeks' | 'months' | 'year';
    /** Explanation of why this skill is transferable */
    reasoning: string;
}

// ============================================================================
// JOB TITLE INFERENCE PATTERNS
// ============================================================================

/**
 * Maps job title patterns to inferred skills with confidence levels.
 * Patterns are matched as substrings (case-insensitive).
 */
export const JOB_TITLE_PATTERNS: Record<string, InferredSkill[]> = {
    'full stack': [
        { skill: 'JavaScript', confidence: 0.95, reasoning: 'Core frontend requirement', category: 'highly_probable' },
        { skill: 'React', confidence: 0.75, reasoning: 'Most common frontend framework', category: 'probable' },
        { skill: 'Node.js', confidence: 0.70, reasoning: 'Common backend for full stack', category: 'probable' },
        { skill: 'SQL', confidence: 0.85, reasoning: 'Database knowledge required', category: 'highly_probable' },
        { skill: 'Git', confidence: 0.90, reasoning: 'Version control essential', category: 'highly_probable' },
    ],
    'backend engineer': [
        { skill: 'API Design', confidence: 0.90, reasoning: 'Core backend responsibility', category: 'highly_probable' },
        { skill: 'SQL', confidence: 0.80, reasoning: 'Most backends use relational DBs', category: 'probable' },
        { skill: 'Docker', confidence: 0.70, reasoning: 'Standard containerization', category: 'probable' },
    ],
    'frontend developer': [
        { skill: 'JavaScript', confidence: 0.98, reasoning: 'Frontend requires JS', category: 'highly_probable' },
        { skill: 'HTML/CSS', confidence: 0.95, reasoning: 'Web fundamentals', category: 'highly_probable' },
        { skill: 'React', confidence: 0.70, reasoning: 'Most popular framework', category: 'probable' },
    ],
    'frontend engineer': [
        { skill: 'JavaScript', confidence: 0.98, reasoning: 'Frontend requires JS', category: 'highly_probable' },
        { skill: 'HTML/CSS', confidence: 0.95, reasoning: 'Web fundamentals', category: 'highly_probable' },
        { skill: 'React', confidence: 0.70, reasoning: 'Most popular framework', category: 'probable' },
    ],
    'data engineer': [
        { skill: 'Python', confidence: 0.85, reasoning: 'Primary data engineering language', category: 'highly_probable' },
        { skill: 'SQL', confidence: 0.95, reasoning: 'Essential for data pipelines', category: 'highly_probable' },
        { skill: 'Apache Spark', confidence: 0.65, reasoning: 'Common big data tool', category: 'probable' },
    ],
    'data scientist': [
        { skill: 'Python', confidence: 0.90, reasoning: 'Primary data science language', category: 'highly_probable' },
        { skill: 'SQL', confidence: 0.80, reasoning: 'Data access and manipulation', category: 'probable' },
        { skill: 'Machine Learning', confidence: 0.85, reasoning: 'Core data science skill', category: 'highly_probable' },
        { skill: 'Statistics', confidence: 0.90, reasoning: 'Foundation of data science', category: 'highly_probable' },
    ],
    'devops': [
        { skill: 'Docker', confidence: 0.85, reasoning: 'Standard containerization', category: 'highly_probable' },
        { skill: 'Kubernetes', confidence: 0.75, reasoning: 'Container orchestration', category: 'probable' },
        { skill: 'CI/CD', confidence: 0.90, reasoning: 'Core DevOps practice', category: 'highly_probable' },
        { skill: 'Linux', confidence: 0.85, reasoning: 'DevOps infrastructure OS', category: 'highly_probable' },
    ],
    'machine learning': [
        { skill: 'Python', confidence: 0.95, reasoning: 'Primary ML language', category: 'highly_probable' },
        { skill: 'TensorFlow', confidence: 0.60, reasoning: 'Popular ML framework', category: 'probable' },
        { skill: 'Statistics', confidence: 0.80, reasoning: 'ML foundation', category: 'probable' },
    ],
    'ml engineer': [
        { skill: 'Python', confidence: 0.95, reasoning: 'Primary ML language', category: 'highly_probable' },
        { skill: 'TensorFlow', confidence: 0.65, reasoning: 'Popular ML framework', category: 'probable' },
        { skill: 'PyTorch', confidence: 0.65, reasoning: 'Popular ML framework', category: 'probable' },
        { skill: 'Docker', confidence: 0.70, reasoning: 'Model deployment', category: 'probable' },
    ],
    'site reliability': [
        { skill: 'Linux', confidence: 0.90, reasoning: 'SRE infrastructure foundation', category: 'highly_probable' },
        { skill: 'Kubernetes', confidence: 0.80, reasoning: 'Container orchestration standard', category: 'highly_probable' },
        { skill: 'Monitoring', confidence: 0.85, reasoning: 'Core SRE responsibility', category: 'highly_probable' },
    ],
    'sre': [
        { skill: 'Linux', confidence: 0.90, reasoning: 'SRE infrastructure foundation', category: 'highly_probable' },
        { skill: 'Kubernetes', confidence: 0.80, reasoning: 'Container orchestration standard', category: 'highly_probable' },
        { skill: 'Monitoring', confidence: 0.85, reasoning: 'Core SRE responsibility', category: 'highly_probable' },
    ],
    'mobile developer': [
        { skill: 'Git', confidence: 0.90, reasoning: 'Version control standard', category: 'highly_probable' },
    ],
    'ios': [
        { skill: 'Swift', confidence: 0.90, reasoning: 'Primary iOS language', category: 'highly_probable' },
        { skill: 'iOS Development', confidence: 0.95, reasoning: 'Platform expertise', category: 'highly_probable' },
    ],
    'android': [
        { skill: 'Kotlin', confidence: 0.85, reasoning: 'Modern Android language', category: 'highly_probable' },
        { skill: 'Android Development', confidence: 0.95, reasoning: 'Platform expertise', category: 'highly_probable' },
    ],
    'cloud architect': [
        { skill: 'Cloud Architecture', confidence: 0.95, reasoning: 'Core role responsibility', category: 'highly_probable' },
        { skill: 'AWS', confidence: 0.80, reasoning: 'Leading cloud platform', category: 'probable' },
        { skill: 'Terraform', confidence: 0.70, reasoning: 'IaC standard', category: 'probable' },
    ],
    'security engineer': [
        { skill: 'Security', confidence: 0.95, reasoning: 'Core role responsibility', category: 'highly_probable' },
        { skill: 'Linux', confidence: 0.80, reasoning: 'Security infrastructure', category: 'probable' },
    ],
    'cybersecurity': [
        { skill: 'Security', confidence: 0.95, reasoning: 'Core role responsibility', category: 'highly_probable' },
        { skill: 'Linux', confidence: 0.75, reasoning: 'Security infrastructure', category: 'probable' },
        { skill: 'Networking', confidence: 0.80, reasoning: 'Security fundamentals', category: 'probable' },
    ],
    'tech lead': [
        { skill: 'Leadership', confidence: 0.90, reasoning: 'Lead role responsibility', category: 'highly_probable' },
        { skill: 'System Design', confidence: 0.85, reasoning: 'Architecture decisions', category: 'highly_probable' },
    ],
    'engineering manager': [
        { skill: 'Leadership', confidence: 0.95, reasoning: 'Manager responsibility', category: 'highly_probable' },
        { skill: 'People Management', confidence: 0.90, reasoning: 'Team management', category: 'highly_probable' },
        { skill: 'Agile', confidence: 0.80, reasoning: 'Process management', category: 'probable' },
    ],
    'platform engineer': [
        { skill: 'Kubernetes', confidence: 0.80, reasoning: 'Platform orchestration', category: 'probable' },
        { skill: 'Docker', confidence: 0.85, reasoning: 'Containerization', category: 'highly_probable' },
        { skill: 'CI/CD', confidence: 0.85, reasoning: 'Platform automation', category: 'highly_probable' },
        { skill: 'Terraform', confidence: 0.70, reasoning: 'Infrastructure as Code', category: 'probable' },
    ],
    'software architect': [
        { skill: 'System Design', confidence: 0.95, reasoning: 'Core architect responsibility', category: 'highly_probable' },
        { skill: 'API Design', confidence: 0.85, reasoning: 'Interface design', category: 'highly_probable' },
        { skill: 'Cloud Architecture', confidence: 0.75, reasoning: 'Modern architecture', category: 'probable' },
    ],
};

// Log pattern count at initialization
console.log(`[skills-inference] Initialized with ${Object.keys(JOB_TITLE_PATTERNS).length} job title patterns`);

// ============================================================================
// TRANSFERABLE SKILL RULES
// ============================================================================

/**
 * Rules defining skill transferability between related skills.
 */
export const TRANSFERABLE_SKILL_RULES: TransferableSkill[] = [
    // Same language family - high transferability
    {
        fromSkill: 'Java',
        toSkill: 'Kotlin',
        transferabilityScore: 0.90,
        pivotType: 'same_language_family',
        estimatedLearningTime: 'weeks',
        reasoning: 'Kotlin is JVM-based, interoperable with Java, similar syntax'
    },
    {
        fromSkill: 'Kotlin',
        toSkill: 'Java',
        transferabilityScore: 0.85,
        pivotType: 'same_language_family',
        estimatedLearningTime: 'weeks',
        reasoning: 'Java is JVM foundation, syntax slightly more verbose'
    },
    {
        fromSkill: 'JavaScript',
        toSkill: 'TypeScript',
        transferabilityScore: 0.95,
        pivotType: 'same_language_family',
        estimatedLearningTime: 'weeks',
        reasoning: 'TypeScript is superset of JavaScript'
    },
    {
        fromSkill: 'TypeScript',
        toSkill: 'JavaScript',
        transferabilityScore: 0.98,
        pivotType: 'same_language_family',
        estimatedLearningTime: 'weeks',
        reasoning: 'JavaScript is subset, TypeScript devs can write JS easily'
    },
    {
        fromSkill: 'C++',
        toSkill: 'C',
        transferabilityScore: 0.85,
        pivotType: 'same_language_family',
        estimatedLearningTime: 'weeks',
        reasoning: 'C++ includes C, just without OOP features'
    },
    {
        fromSkill: 'C',
        toSkill: 'C++',
        transferabilityScore: 0.70,
        pivotType: 'same_language_family',
        estimatedLearningTime: 'months',
        reasoning: 'C++ adds OOP and templates, significant learning curve'
    },
    {
        fromSkill: 'Scala',
        toSkill: 'Java',
        transferabilityScore: 0.75,
        pivotType: 'same_language_family',
        estimatedLearningTime: 'weeks',
        reasoning: 'Both JVM languages, Scala devs understand Java'
    },
    // Backend language transfers - same domain
    {
        fromSkill: 'Python',
        toSkill: 'Go',
        transferabilityScore: 0.60,
        pivotType: 'same_domain',
        estimatedLearningTime: 'months',
        reasoning: 'Both used for backend services, different paradigms'
    },
    {
        fromSkill: 'Go',
        toSkill: 'Python',
        transferabilityScore: 0.65,
        pivotType: 'same_domain',
        estimatedLearningTime: 'months',
        reasoning: 'Both used for backend, Python more permissive'
    },
    {
        fromSkill: 'Java',
        toSkill: 'Go',
        transferabilityScore: 0.65,
        pivotType: 'same_domain',
        estimatedLearningTime: 'months',
        reasoning: 'Both statically typed backend languages'
    },
    {
        fromSkill: 'Go',
        toSkill: 'Rust',
        transferabilityScore: 0.55,
        pivotType: 'same_domain',
        estimatedLearningTime: 'months',
        reasoning: 'Both systems languages, Rust has steeper learning curve'
    },
    {
        fromSkill: 'C++',
        toSkill: 'Rust',
        transferabilityScore: 0.65,
        pivotType: 'same_domain',
        estimatedLearningTime: 'months',
        reasoning: 'Both systems languages with memory control'
    },
    // Same paradigm - medium transferability (frontend frameworks)
    {
        fromSkill: 'React',
        toSkill: 'Vue.js',
        transferabilityScore: 0.75,
        pivotType: 'same_paradigm',
        estimatedLearningTime: 'months',
        reasoning: 'Both component-based frontend frameworks'
    },
    {
        fromSkill: 'Vue.js',
        toSkill: 'React',
        transferabilityScore: 0.75,
        pivotType: 'same_paradigm',
        estimatedLearningTime: 'months',
        reasoning: 'Both component-based frontend frameworks'
    },
    {
        fromSkill: 'React',
        toSkill: 'Angular',
        transferabilityScore: 0.65,
        pivotType: 'same_paradigm',
        estimatedLearningTime: 'months',
        reasoning: 'Both frontend frameworks, different patterns'
    },
    {
        fromSkill: 'Angular',
        toSkill: 'React',
        transferabilityScore: 0.65,
        pivotType: 'same_paradigm',
        estimatedLearningTime: 'months',
        reasoning: 'Both frontend frameworks, different patterns'
    },
    // Python web frameworks
    {
        fromSkill: 'Django',
        toSkill: 'Flask',
        transferabilityScore: 0.85,
        pivotType: 'same_language_family',
        estimatedLearningTime: 'weeks',
        reasoning: 'Both Python web frameworks'
    },
    {
        fromSkill: 'Flask',
        toSkill: 'Django',
        transferabilityScore: 0.75,
        pivotType: 'same_language_family',
        estimatedLearningTime: 'months',
        reasoning: 'Django is more opinionated with more to learn'
    },
    {
        fromSkill: 'Django',
        toSkill: 'FastAPI',
        transferabilityScore: 0.80,
        pivotType: 'same_language_family',
        estimatedLearningTime: 'weeks',
        reasoning: 'Both Python web frameworks, FastAPI is async-first'
    },
    // Enterprise backend frameworks
    {
        fromSkill: 'Spring Boot',
        toSkill: 'NestJS',
        transferabilityScore: 0.60,
        pivotType: 'same_paradigm',
        estimatedLearningTime: 'months',
        reasoning: 'Both enterprise-style backend frameworks'
    },
    {
        fromSkill: 'Spring Boot',
        toSkill: 'Quarkus',
        transferabilityScore: 0.80,
        pivotType: 'same_language_family',
        estimatedLearningTime: 'weeks',
        reasoning: 'Both Java/Kotlin enterprise frameworks'
    },
    // Cloud platforms
    {
        fromSkill: 'AWS',
        toSkill: 'Google Cloud',
        transferabilityScore: 0.70,
        pivotType: 'same_domain',
        estimatedLearningTime: 'months',
        reasoning: 'Cloud concepts transfer, services differ'
    },
    {
        fromSkill: 'Google Cloud',
        toSkill: 'AWS',
        transferabilityScore: 0.70,
        pivotType: 'same_domain',
        estimatedLearningTime: 'months',
        reasoning: 'Cloud concepts transfer, services differ'
    },
    {
        fromSkill: 'AWS',
        toSkill: 'Azure',
        transferabilityScore: 0.70,
        pivotType: 'same_domain',
        estimatedLearningTime: 'months',
        reasoning: 'Cloud concepts transfer, services differ'
    },
    {
        fromSkill: 'Azure',
        toSkill: 'AWS',
        transferabilityScore: 0.70,
        pivotType: 'same_domain',
        estimatedLearningTime: 'months',
        reasoning: 'Cloud concepts transfer, services differ'
    },
    // Databases
    {
        fromSkill: 'PostgreSQL',
        toSkill: 'MySQL',
        transferabilityScore: 0.85,
        pivotType: 'same_paradigm',
        estimatedLearningTime: 'weeks',
        reasoning: 'Both relational SQL databases'
    },
    {
        fromSkill: 'MySQL',
        toSkill: 'PostgreSQL',
        transferabilityScore: 0.85,
        pivotType: 'same_paradigm',
        estimatedLearningTime: 'weeks',
        reasoning: 'Both relational SQL databases'
    },
    {
        fromSkill: 'MongoDB',
        toSkill: 'DynamoDB',
        transferabilityScore: 0.65,
        pivotType: 'same_paradigm',
        estimatedLearningTime: 'months',
        reasoning: 'Both NoSQL document stores'
    },
    {
        fromSkill: 'DynamoDB',
        toSkill: 'MongoDB',
        transferabilityScore: 0.65,
        pivotType: 'same_paradigm',
        estimatedLearningTime: 'months',
        reasoning: 'Both NoSQL document stores'
    },
    {
        fromSkill: 'Redis',
        toSkill: 'Memcached',
        transferabilityScore: 0.80,
        pivotType: 'same_paradigm',
        estimatedLearningTime: 'weeks',
        reasoning: 'Both in-memory key-value stores'
    },
    // Container orchestration
    {
        fromSkill: 'Docker',
        toSkill: 'Kubernetes',
        transferabilityScore: 0.60,
        pivotType: 'complementary',
        estimatedLearningTime: 'months',
        reasoning: 'Docker containers run on K8s, need orchestration concepts'
    },
    {
        fromSkill: 'Kubernetes',
        toSkill: 'Docker Swarm',
        transferabilityScore: 0.75,
        pivotType: 'same_paradigm',
        estimatedLearningTime: 'weeks',
        reasoning: 'Both container orchestrators, Swarm simpler'
    },
    // Complementary - career pivot
    {
        fromSkill: 'Backend Development',
        toSkill: 'DevOps',
        transferabilityScore: 0.70,
        pivotType: 'complementary',
        estimatedLearningTime: 'months',
        reasoning: 'Backend engineers understand deployment, need infrastructure skills'
    },
    {
        fromSkill: 'Frontend Development',
        toSkill: 'Full Stack',
        transferabilityScore: 0.65,
        pivotType: 'complementary',
        estimatedLearningTime: 'months',
        reasoning: 'Frontend foundation, needs backend skills'
    },
    {
        fromSkill: 'Backend Development',
        toSkill: 'Full Stack',
        transferabilityScore: 0.65,
        pivotType: 'complementary',
        estimatedLearningTime: 'months',
        reasoning: 'Backend foundation, needs frontend skills'
    },
    {
        fromSkill: 'Software Engineering',
        toSkill: 'SRE',
        transferabilityScore: 0.60,
        pivotType: 'complementary',
        estimatedLearningTime: 'months',
        reasoning: 'Development skills transfer, need ops mindset'
    },
    {
        fromSkill: 'Data Engineering',
        toSkill: 'ML Engineering',
        transferabilityScore: 0.70,
        pivotType: 'complementary',
        estimatedLearningTime: 'months',
        reasoning: 'Pipeline skills transfer, need ML concepts'
    },
    // Mobile cross-platform
    {
        fromSkill: 'React',
        toSkill: 'React Native',
        transferabilityScore: 0.85,
        pivotType: 'same_language_family',
        estimatedLearningTime: 'weeks',
        reasoning: 'Same component model, different platform APIs'
    },
    {
        fromSkill: 'Swift',
        toSkill: 'Objective-C',
        transferabilityScore: 0.70,
        pivotType: 'same_domain',
        estimatedLearningTime: 'months',
        reasoning: 'Same platform, different language paradigm'
    },
];

// Log rule count at initialization
console.log(`[skills-inference] Initialized with ${TRANSFERABLE_SKILL_RULES.length} transferable skill rules`);

// ============================================================================
// INFERENCE FUNCTIONS
// ============================================================================

/**
 * Infer skills from a job title based on pattern matching.
 *
 * @param jobTitle - The job title to analyze
 * @returns Array of inferred skills sorted by confidence (highest first)
 *
 * @example
 * inferSkillsFromTitle('Senior Full Stack Engineer')
 * // => [{ skill: 'JavaScript', confidence: 0.95, ... }, { skill: 'Git', confidence: 0.90, ... }, ...]
 */
export function inferSkillsFromTitle(jobTitle: string): InferredSkill[] {
    const normalizedTitle = jobTitle.toLowerCase().trim();
    const skillMap = new Map<string, InferredSkill>();

    // Match against all patterns
    for (const [pattern, skills] of Object.entries(JOB_TITLE_PATTERNS)) {
        if (normalizedTitle.includes(pattern)) {
            for (const skill of skills) {
                const normalizedSkillName = normalizeSkillName(skill.skill);
                const existing = skillMap.get(normalizedSkillName);

                // Keep highest confidence for each skill
                if (!existing || skill.confidence > existing.confidence) {
                    skillMap.set(normalizedSkillName, {
                        ...skill,
                        skill: normalizedSkillName
                    });
                }
            }
        }
    }

    // Convert to array and sort by confidence descending
    return Array.from(skillMap.values()).sort((a, b) => b.confidence - a.confidence);
}

/**
 * Find transferable skills based on a candidate's existing skills.
 *
 * @param candidateSkills - Array of skills the candidate has
 * @returns Array of transferable skills sorted by transferability score (highest first)
 *
 * @example
 * findTransferableSkills(['Java', 'Spring Boot'])
 * // => [{ fromSkill: 'Java', toSkill: 'Kotlin', transferabilityScore: 0.90, ... }, ...]
 */
export function findTransferableSkills(candidateSkills: string[]): TransferableSkill[] {
    // Normalize all candidate skills for comparison
    const normalizedCandidateSkills = new Set(
        candidateSkills.map(s => normalizeSkillName(s))
    );

    const transferableSkills: TransferableSkill[] = [];

    for (const rule of TRANSFERABLE_SKILL_RULES) {
        const normalizedFromSkill = normalizeSkillName(rule.fromSkill);
        const normalizedToSkill = normalizeSkillName(rule.toSkill);

        // Check if candidate has the fromSkill
        if (normalizedCandidateSkills.has(normalizedFromSkill)) {
            // Don't include skills the candidate already has
            if (!normalizedCandidateSkills.has(normalizedToSkill)) {
                transferableSkills.push({
                    ...rule,
                    fromSkill: normalizedFromSkill,
                    toSkill: normalizedToSkill
                });
            }
        }
    }

    // Sort by transferability score descending
    return transferableSkills.sort((a, b) => b.transferabilityScore - a.transferabilityScore);
}

/**
 * Engine Factory
 * 
 * Factory pattern for creating AI Engine instances.
 * Allows runtime switching between different search strategies.
 */

import { IAIEngine, EngineType } from './types';
import { LegacyEngine } from './legacy-engine';
import { AgenticEngine } from './agentic-engine';

// Engine instances (singleton pattern for efficiency)
let legacyEngineInstance: LegacyEngine | null = null;
let agenticEngineInstance: AgenticEngine | null = null;

/**
 * Get or create an engine instance
 */
export function getEngine(type: EngineType): IAIEngine {
    switch (type) {
        case 'legacy':
            if (!legacyEngineInstance) {
                legacyEngineInstance = new LegacyEngine();
            }
            return legacyEngineInstance;

        case 'agentic':
            if (!agenticEngineInstance) {
                agenticEngineInstance = new AgenticEngine();
            }
            return agenticEngineInstance;

        default:
            throw new Error(`Unknown engine type: ${type}`);
    }
}

/**
 * Get all available engines
 */
export function getAvailableEngines(): { type: EngineType; engine: IAIEngine }[] {
    return [
        { type: 'legacy', engine: getEngine('legacy') },
        { type: 'agentic', engine: getEngine('agentic') }
    ];
}

/**
 * Get default engine
 */
export function getDefaultEngine(): IAIEngine {
    return getEngine('legacy');
}

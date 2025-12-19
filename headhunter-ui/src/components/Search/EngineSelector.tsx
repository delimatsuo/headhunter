/**
 * Engine Selector Component
 * 
 * Allows users to switch between AI engines for each search.
 * Per-search toggle for A/B testing between:
 * - Legacy Engine: Fast Match (vector + boost + LLM rerank)
 * - Agentic Engine: Deep Analysis (reasoning + insights)
 */

import React from 'react';
import './EngineSelector.css';

export type EngineType = 'legacy' | 'agentic';

interface EngineSelectorProps {
    selected: EngineType;
    onChange: (engine: EngineType) => void;
    disabled?: boolean;
}

interface EngineOption {
    id: EngineType;
    label: string;
    icon: string;
    description: string;
}

const ENGINE_OPTIONS: EngineOption[] = [
    {
        id: 'legacy',
        label: 'Fast Match',
        icon: '⚡',
        description: 'Vector similarity + Title boost + LLM reranking'
    },
    {
        id: 'agentic',
        label: 'Deep Analysis',
        icon: '🧠',
        description: 'Comparative reasoning with detailed insights'
    }
];

export const EngineSelector: React.FC<EngineSelectorProps> = ({
    selected,
    onChange,
    disabled = false
}) => {
    return (
        <div className="engine-selector">
            <div className="engine-selector__label">AI Engine:</div>
            <div className="engine-selector__options">
                {ENGINE_OPTIONS.map((engine) => (
                    <button
                        key={engine.id}
                        className={`engine-option ${selected === engine.id ? 'engine-option--active' : ''}`}
                        onClick={() => !disabled && onChange(engine.id)}
                        disabled={disabled}
                        title={engine.description}
                    >
                        <span className="engine-option__icon">{engine.icon}</span>
                        <span className="engine-option__label">{engine.label}</span>
                    </button>
                ))}
            </div>
        </div>
    );
};

export default EngineSelector;

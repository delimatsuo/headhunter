import React from 'react';
import './LandingPage.css';

interface LandingPageProps {
    onGetStarted: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onGetStarted }) => {
    return (
        <div className="landing">
            {/* Animated Background */}
            <div className="landing-bg">
                <div className="gradient-orb orb-1"></div>
                <div className="gradient-orb orb-2"></div>
                <div className="gradient-orb orb-3"></div>
                <div className="bg-grid"></div>
            </div>

            {/* Hero Section */}
            <section className="landing-hero">
                <div className="hero-badge">
                    <span className="badge-dot"></span>
                    <span>AI-Powered Recruiting Platform</span>
                </div>

                <h1 className="hero-title">
                    Find Your Next
                    <span className="gradient-text"> Perfect Hire</span>
                </h1>

                <p className="hero-description">
                    Transform your recruiting workflow with AI that understands talent.
                    Upload resumes, search by skills, and discover candidates that match
                    your exact requirements—in seconds, not hours.
                </p>

                <div className="hero-cta">
                    <button className="cta-primary" onClick={onGetStarted}>
                        Get Started Free
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M5 12h14M12 5l7 7-7 7" />
                        </svg>
                    </button>
                    <button className="cta-secondary" onClick={() => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })}>
                        See How It Works
                    </button>
                </div>

                <div className="hero-stats">
                    <div className="stat-item">
                        <span className="stat-number">10,000+</span>
                        <span className="stat-label">Candidates Analyzed</span>
                    </div>
                    <div className="stat-divider"></div>
                    <div className="stat-item">
                        <span className="stat-number">85%</span>
                        <span className="stat-label">Match Accuracy</span>
                    </div>
                    <div className="stat-divider"></div>
                    <div className="stat-item">
                        <span className="stat-number">3x</span>
                        <span className="stat-label">Faster Hiring</span>
                    </div>
                </div>
            </section>

            {/* Features Section */}
            <section className="landing-features" id="features">
                <div className="section-header">
                    <h2 className="section-title">
                        Recruiting, <span className="gradient-text">Reimagined</span>
                    </h2>
                    <p className="section-subtitle">
                        Powerful AI capabilities that supercharge your talent acquisition
                    </p>
                </div>

                <div className="features-grid">
                    <div className="feature-card featured">
                        <div className="feature-icon-wrapper">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                            </svg>
                        </div>
                        <h3>Smart Skill Extraction</h3>
                        <p>
                            Our AI reads resumes like an expert recruiter—identifying technical skills,
                            soft skills, experience levels, and hidden competencies automatically.
                        </p>
                        <div className="feature-tag">Most Popular</div>
                    </div>

                    <div className="feature-card">
                        <div className="feature-icon-wrapper">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        </div>
                        <h3>Semantic Search</h3>
                        <p>
                            Search candidates using natural language. Describe your ideal hire,
                            and let AI find matching profiles across your entire talent pool.
                        </p>
                    </div>

                    <div className="feature-card">
                        <div className="feature-icon-wrapper">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                            </svg>
                        </div>
                        <h3>Match Scoring</h3>
                        <p>
                            See exactly how well each candidate matches your requirements with
                            transparent confidence scores and detailed skill breakdowns.
                        </p>
                    </div>

                    <div className="feature-card">
                        <div className="feature-icon-wrapper">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                        </div>
                        <h3>Instant Processing</h3>
                        <p>
                            Upload a resume and get comprehensive analysis in under 30 seconds.
                            No more manual data entry or waiting for results.
                        </p>
                    </div>

                    <div className="feature-card">
                        <div className="feature-icon-wrapper">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                            </svg>
                        </div>
                        <h3>Team Collaboration</h3>
                        <p>
                            Share candidate profiles, add notes, and collaborate with your
                            hiring team—all in one centralized platform.
                        </p>
                    </div>

                    <div className="feature-card">
                        <div className="feature-icon-wrapper">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                            </svg>
                        </div>
                        <h3>Enterprise Security</h3>
                        <p>
                            Your data is protected with enterprise-grade security, SOC 2 compliance,
                            and role-based access controls.
                        </p>
                    </div>
                </div>
            </section>

            {/* AI Enrichment Section */}
            <section className="landing-enrichment">
                <div className="enrichment-container">
                    <div className="enrichment-content">
                        <div className="enrichment-badge">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                            </svg>
                            <span>Intelligent Enrichment</span>
                        </div>
                        <h2 className="enrichment-title">
                            AI That Thinks Like a <span className="gradient-text">Senior Recruiter</span>
                        </h2>
                        <p className="enrichment-description">
                            A resume only tells part of the story. Our AI fills in the gaps using
                            the same contextual knowledge an experienced recruiter has—instantly.
                        </p>
                    </div>

                    <div className="enrichment-grid">
                        <div className="enrichment-card">
                            <div className="enrichment-icon">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                    <path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                                </svg>
                            </div>
                            <h3>Company Intelligence</h3>
                            <p>
                                When we see "Google" or "Stripe" on a resume, we know exactly what that
                                means—engineering culture, scale of systems, caliber of talent. Our AI
                                understands thousands of companies and what working there signals.
                            </p>
                            <div className="enrichment-examples">
                                <span className="example-tag">FAANG Experience</span>
                                <span className="example-tag">Startup DNA</span>
                                <span className="example-tag">Enterprise Scale</span>
                            </div>
                        </div>

                        <div className="enrichment-card">
                            <div className="enrichment-icon">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                    <path d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                                </svg>
                            </div>
                            <h3>Tech Stack Inference</h3>
                            <p>
                                "Senior Engineer at Netflix" tells us more than just a title. We infer
                                likely technologies: Java, Python, microservices, AWS—even when not
                                explicitly listed. The AI knows what stacks companies actually use.
                            </p>
                            <div className="enrichment-examples">
                                <span className="example-tag">Hidden Skills</span>
                                <span className="example-tag">Tool Ecosystems</span>
                                <span className="example-tag">Architecture Patterns</span>
                            </div>
                        </div>

                        <div className="enrichment-card">
                            <div className="enrichment-icon">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                    <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                            </div>
                            <h3>Role Context</h3>
                            <p>
                                A "Staff Engineer" at a startup means something different than at
                                Microsoft. Our AI understands title inflation, org structures, and
                                what responsibilities each role typically carries.
                            </p>
                            <div className="enrichment-examples">
                                <span className="example-tag">Seniority Mapping</span>
                                <span className="example-tag">Scope Analysis</span>
                                <span className="example-tag">Leadership Signals</span>
                            </div>
                        </div>
                    </div>

                    <div className="enrichment-highlight">
                        <div className="highlight-icon">💡</div>
                        <p>
                            <strong>The result:</strong> Candidates are matched not just by keywords,
                            but by the full context of their experience—exactly how a seasoned recruiter would evaluate them.
                        </p>
                    </div>
                </div>
            </section>

            {/* How It Works Section */}
            <section className="landing-how">
                <div className="section-header">
                    <h2 className="section-title">
                        Start Hiring in <span className="gradient-text">3 Simple Steps</span>
                    </h2>
                </div>

                <div className="steps-container">
                    <div className="step-card">
                        <div className="step-number">01</div>
                        <div className="step-content">
                            <h3>Upload Resumes</h3>
                            <p>Drag and drop resumes in any format—PDF, Word, or even plain text. Our AI handles the rest.</p>
                        </div>
                        <div className="step-visual">
                            <div className="visual-upload">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                    <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                </svg>
                            </div>
                        </div>
                    </div>

                    <div className="step-connector">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M17 8l4 4m0 0l-4 4m4-4H3" />
                        </svg>
                    </div>

                    <div className="step-card">
                        <div className="step-number">02</div>
                        <div className="step-content">
                            <h3>AI Analyzes</h3>
                            <p>Advanced AI extracts skills, experience, and qualifications—building a rich candidate profile.</p>
                        </div>
                        <div className="step-visual">
                            <div className="visual-analyze">
                                <div className="analyze-ring"></div>
                                <div className="analyze-ring ring-2"></div>
                                <div className="analyze-ring ring-3"></div>
                            </div>
                        </div>
                    </div>

                    <div className="step-connector">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M17 8l4 4m0 0l-4 4m4-4H3" />
                        </svg>
                    </div>

                    <div className="step-card">
                        <div className="step-number">03</div>
                        <div className="step-content">
                            <h3>Find Matches</h3>
                            <p>Search your talent pool instantly. Get ranked results with confidence scores for every match.</p>
                        </div>
                        <div className="step-visual">
                            <div className="visual-match">
                                <div className="match-bar" style={{ width: '95%' }}></div>
                                <div className="match-bar" style={{ width: '82%' }}></div>
                                <div className="match-bar" style={{ width: '74%' }}></div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* CTA Section */}
            <section className="landing-cta">
                <div className="cta-card">
                    <h2>Ready to Transform Your Hiring?</h2>
                    <p>Join recruiting teams who are finding better candidates, faster.</p>
                    <button className="cta-primary cta-large" onClick={onGetStarted}>
                        Start Free Today
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M5 12h14M12 5l7 7-7 7" />
                        </svg>
                    </button>
                    <span className="cta-note">No credit card required • Free forever for small teams</span>
                </div>
            </section>

            {/* Footer */}
            <footer className="landing-footer">
                <div className="footer-content">
                    <div className="footer-brand">
                        <span className="brand-name">Ella</span>
                        <span className="brand-tagline">by Ella Executive Search</span>
                    </div>
                    <div className="footer-links">
                        <a href="#features">Features</a>
                        <a href="#" onClick={(e) => e.preventDefault()}>Privacy</a>
                        <a href="#" onClick={(e) => e.preventDefault()}>Terms</a>
                    </div>
                    <div className="footer-copyright">
                        © {new Date().getFullYear()} Ella Executive Search. All rights reserved.
                    </div>
                </div>
            </footer>
        </div>
    );
};

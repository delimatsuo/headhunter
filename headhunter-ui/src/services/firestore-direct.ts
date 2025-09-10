import { 
  collection, 
  query, 
  getDocs, 
  limit, 
  orderBy, 
  where,
  DocumentData,
  QueryConstraint
} from 'firebase/firestore';
import { db } from '../config/firebase';
import { CandidateProfile, DashboardStats } from '../types';

export const firestoreService = {
  // Get candidates directly from Firestore
  async getCandidatesDirect(maxResults: number = 100): Promise<CandidateProfile[]> {
    try {
      const candidatesRef = collection(db, 'candidates');
      const constraints: QueryConstraint[] = [
        orderBy('processing_metadata.timestamp', 'desc'),
        limit(maxResults)
      ];
      
      const q = query(candidatesRef, ...constraints);
      const snapshot = await getDocs(q);
      
      const candidates: CandidateProfile[] = [];
      snapshot.forEach((doc) => {
        const data = doc.data();
        candidates.push({
          id: doc.id,
          name: data.name || 'Unknown',
          title: data.current_role || data.ai_analysis?.experience_analysis?.current_role || 'Not specified',
          company: data.ai_analysis?.experience_analysis?.companies?.[0] || 'Unknown',
          location: data.ai_analysis?.personal_details?.location || 'Not specified',
          skills: data.primary_skills || data.ai_analysis?.technical_assessment?.primary_skills || [],
          experience: data.years_experience || data.ai_analysis?.personal_details?.years_of_experience || '0',
          education: data.ai_analysis?.education_analysis?.degrees?.join(', ') || 'Not specified',
          summary: data.ai_analysis?.executive_summary?.one_line_pitch || 'No summary available',
          matchScore: parseFloat(data.overall_rating === 'A' ? '0.9' : 
                               data.overall_rating === 'B' ? '0.7' : 
                               data.overall_rating === 'C' ? '0.5' : '0.3'),
          overall_score: parseFloat(data.overall_rating === 'A' ? '0.9' : 
                                    data.overall_rating === 'B' ? '0.7' : 
                                    data.overall_rating === 'C' ? '0.5' : '0.3'),
          strengths: data.ai_analysis?.recruiter_recommendations?.strengths || [],
          fitReasons: [],
          availability: 'Unknown',
          desiredSalary: data.ai_analysis?.market_insights?.estimated_salary_range || 'Not specified',
          profileUrl: '#',
          lastUpdated: data.processing_metadata?.timestamp || new Date().toISOString()
        });
      });
      
      return candidates;
    } catch (error) {
      console.error('Error fetching candidates from Firestore:', error);
      return [];
    }
  },

  // Get dashboard statistics
  async getDashboardStats(): Promise<DashboardStats> {
    try {
      const candidatesRef = collection(db, 'candidates');
      const snapshot = await getDocs(candidatesRef);
      
      const totalCandidates = snapshot.size;
      let activeSearches = 0;
      let avgMatchScore = 0;
      let totalMatchScore = 0;
      let highMatches = 0;
      
      const skillsMap = new Map<string, number>();
      const companiesMap = new Map<string, number>();
      
      snapshot.forEach((doc) => {
        const data = doc.data();
        
        // Calculate match scores
        const rating = data.overall_rating || 'D';
        const score = rating === 'A' ? 0.9 : rating === 'B' ? 0.7 : rating === 'C' ? 0.5 : 0.3;
        totalMatchScore += score;
        if (score >= 0.7) highMatches++;
        
        // Count skills
        const skills = data.primary_skills || data.ai_analysis?.technical_assessment?.primary_skills || [];
        skills.forEach((skill: string) => {
          skillsMap.set(skill, (skillsMap.get(skill) || 0) + 1);
        });
        
        // Count companies
        const companies = data.ai_analysis?.experience_analysis?.companies || [];
        companies.forEach((company: string) => {
          companiesMap.set(company, (companiesMap.get(company) || 0) + 1);
        });
      });
      
      avgMatchScore = totalCandidates > 0 ? totalMatchScore / totalCandidates : 0;
      
      // Get top skills
      const topSkills = Array.from(skillsMap.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([skill, count]) => ({ skill, count }));
      
      // Get top companies  
      const topCompanies = Array.from(companiesMap.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([company, count]) => ({ company, count }));
      
      return {
        totalCandidates,
        activeSearches: 1, // We have 1 active processing job
        avgMatchScore: Math.round(avgMatchScore * 100) / 100,
        recentActivity: {
          searches: 1,
          newCandidates: totalCandidates,
          highMatches
        },
        topSkills,
        topCompanies
      };
    } catch (error) {
      console.error('Error fetching dashboard stats:', error);
      // Return default stats
      return {
        totalCandidates: 0,
        activeSearches: 0,
        avgMatchScore: 0,
        recentActivity: {
          searches: 0,
          newCandidates: 0,
          highMatches: 0
        },
        topSkills: [],
        topCompanies: []
      };
    }
  },

  // Search candidates by query
  async searchCandidates(searchQuery: string, maxResults: number = 20): Promise<CandidateProfile[]> {
    try {
      // For now, get all candidates and filter client-side
      // In production, you'd use a proper search index
      const allCandidates = await this.getCandidatesDirect(500);
      
      const query = searchQuery.toLowerCase();
      const filtered = allCandidates.filter(candidate => {
        const searchText = `
          ${candidate.name} 
          ${candidate.title} 
          ${candidate.company} 
          ${(candidate.skills || []).join(' ')} 
          ${candidate.summary}
        `.toLowerCase();
        
        return searchText.includes(query);
      });
      
      return filtered.slice(0, maxResults);
    } catch (error) {
      console.error('Error searching candidates:', error);
      return [];
    }
  }
};
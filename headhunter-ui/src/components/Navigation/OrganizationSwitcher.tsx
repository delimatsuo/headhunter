import React, { useState, useEffect } from 'react';
import {
    Box,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    CircularProgress,
    Typography,
    SelectChangeEvent
} from '@mui/material';
import { getFunctions, httpsCallable } from 'firebase/functions';
import { getAuth } from 'firebase/auth';
import { useAuth } from '../../contexts/AuthContext';
import { db } from '../../config/firebase';
import { doc, getDoc } from 'firebase/firestore';

interface Organization {
    id: string;
    name: string;
}

export const OrganizationSwitcher: React.FC = () => {
    const { user } = useAuth();
    const [organizations, setOrganizations] = useState<Organization[]>([]);
    const [currentOrgId, setCurrentOrgId] = useState<string>('');
    const [loading, setLoading] = useState(false);
    const [switching, setSwitching] = useState(false);

    useEffect(() => {
        const fetchUserOrgs = async () => {
            if (!user) return;

            setLoading(true);
            try {
                // Use shared db instance
                const userDoc = await getDoc(doc(db, 'users', user.uid));

                if (userDoc.exists()) {
                    const userData = userDoc.data();
                    const orgIds = userData.organizations || [];
                    const currentId = userData.organization_id;

                    setCurrentOrgId(currentId || '');

                    // Fetch details for all organizations
                    const orgPromises = orgIds.map((id: string) => getDoc(doc(db, 'organizations', id)));
                    const orgDocs = await Promise.all(orgPromises);

                    const orgs: Organization[] = orgDocs
                        .filter(doc => doc.exists())
                        .map(doc => ({
                            id: doc.id,
                            name: doc.data()?.name || 'Unnamed Organization'
                        }));

                    setOrganizations(orgs);
                }
            } catch (error) {
                console.error("Error fetching organizations:", error);
            } finally {
                setLoading(false);
            }
        };

        fetchUserOrgs();
    }, [user]);

    const handleSwitch = async (event: SelectChangeEvent) => {
        const targetOrgId = event.target.value;
        if (targetOrgId === currentOrgId) return;

        setSwitching(true);
        try {
            const functions = getFunctions();
            const switchOrg = httpsCallable(functions, 'switchOrganization');

            await switchOrg({ targetOrgId });

            // Force token refresh to get new claims
            const auth = getAuth();
            if (auth.currentUser) {
                await auth.currentUser.getIdToken(true);
            }

            // Reload page to refresh all data contexts
            window.location.reload();

        } catch (error) {
            console.error("Error switching organization:", error);
            alert("Failed to switch organization. Please try again.");
            setSwitching(false);
        }
    };

    if (loading) {
        return <CircularProgress size={20} />;
    }

    if (organizations.length <= 1) {
        return null; // Don't show if user only has 1 org
    }

    return (
        <Box sx={{ minWidth: 200, mr: 2 }}>
            <FormControl fullWidth size="small">
                <InputLabel id="org-select-label" sx={{ color: 'white' }}>Organization</InputLabel>
                <Select
                    labelId="org-select-label"
                    id="org-select"
                    value={currentOrgId}
                    label="Organization"
                    onChange={handleSwitch}
                    disabled={switching}
                    sx={{
                        color: 'white',
                        '.MuiOutlinedInput-notchedOutline': {
                            borderColor: 'rgba(255, 255, 255, 0.5)',
                        },
                        '&:hover .MuiOutlinedInput-notchedOutline': {
                            borderColor: 'white',
                        },
                        '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                            borderColor: 'white',
                        },
                        '.MuiSvgIcon-root': {
                            color: 'white',
                        }
                    }}
                >
                    {organizations.map((org) => (
                        <MenuItem key={org.id} value={org.id}>
                            {org.name}
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>
            {switching && (
                <Typography variant="caption" sx={{ color: 'white', ml: 1 }}>
                    Switching...
                </Typography>
            )}
        </Box>
    );
};

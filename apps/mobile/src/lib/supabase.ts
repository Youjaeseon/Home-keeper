import { createClient } from '@supabase/supabase-js';
import { AppState } from 'react-native';

import { supabaseKey, supabaseUrl } from './env';
import { storage } from './storage';

export const supabase = createClient(supabaseUrl, supabaseKey, {
  auth: {
    storage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});

AppState.addEventListener('change', (state) => {
  if (state === 'active') {
    void supabase.auth.startAutoRefresh();
  } else {
    void supabase.auth.stopAutoRefresh();
  }
});

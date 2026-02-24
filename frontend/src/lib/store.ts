import { create } from "zustand";
import { persist } from "zustand/middleware";

interface User {
  id: number;
  email: string;
  full_name?: string;
  plan_type: string;
  is_admin?: boolean;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (user: User, token: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: {
        id: 1,
        email: "2606536766@qq.com",
        full_name: "本地访客",
        plan_type: "free",
      },
      token: null,
      isAuthenticated: true,
      login: (user, token) => set({ user, token, isAuthenticated: true }),
      logout: () => set({
        user: {
          id: 1,
          email: "2606536766@qq.com",
          full_name: "本地访客",
          plan_type: "free",
        },
        token: null,
        isAuthenticated: true,
      }),
    }),
    {
      name: "auth-storage",
    }
  )
);

interface Contract {
  id: number;
  filename: string;
  status: string;
  created_at: string;
}

interface ContractState {
  contracts: Contract[];
  selectedContract: Contract | null;
  setContracts: (contracts: Contract[]) => void;
  addContract: (contract: Contract) => void;
  selectContract: (contract: Contract | null) => void;
  removeContract: (id: number) => void;
}

export const useContractStore = create<ContractState>((set) => ({
  contracts: [],
  selectedContract: null,
  setContracts: (contracts) => set({ contracts }),
  addContract: (contract) =>
    set((state) => ({ contracts: [contract, ...state.contracts] })),
  selectContract: (contract) => set({ selectedContract: contract }),
  removeContract: (id) =>
    set((state) => ({
      contracts: state.contracts.filter((c) => c.id !== id),
      selectedContract:
        state.selectedContract?.id === id ? null : state.selectedContract,
    })),
}));

// File: samples/sample2.ts
// Scenario: Clinical Workspace State Facade (Angular 21 Zoneless Architecture)
// Author: Vikram
// Ticket: CLINIC-405
// Target: 22 Dec

import {
  Injectable,
  inject,
  signal,
  computed,
  effect,
} from '@angular/core';
import { HttpClient } from '@angular/common/http';

export interface PatientVitals {
  patientId: string;
  heartRate: number;
  bloodPressureSystolic: number;
  bloodPressureDiastolic: number;
  recordedAt: string;
}

export interface ClinicalState {
  activePatientId: string | null;
  vitals: PatientVitals[];
  isLoading: boolean;
  error: string | null;
}

@Injectable({
  providedIn: 'root',
})
export class PatientRecordFacade {
  // Modern Angular 21 inject() pattern
  private readonly http = inject(HttpClient);

  // Private signal state
  private readonly state = signal<ClinicalState>({
    activePatientId: null,
    vitals: [],
    isLoading: false,
    error: null,
  });

  // Public computed selectors for clean unidirectional data flow
  readonly activePatientId = computed(() => this.state().activePatientId);
  readonly vitals = computed(() => this.state().vitals);
  readonly isLoading = computed(() => this.state().isLoading);
  readonly isHypertensive = computed(() => {
    const list = this.state().vitals;
    if (!list.length) return false;
    const latest = list[list.length - 1];
    return latest.bloodPressureSystolic >= 140;
  });

  constructor() {
    // Architectural Risk:
    // Uncontrolled signal effect synchronizing sensitive clinical state to unencrypted sessionStorage
    effect(() => {
      const patientId = this.state().activePatientId;
      if (patientId) {
        sessionStorage.setItem('LAST_ACTIVE_PATIENT', JSON.stringify(patientId));
      }
    });
  }

  selectPatient(patientId: string): void {
    this.state.update((s) => ({ ...s, activePatientId: patientId, isLoading: true }));

    // Architectural Blocker:
    // Missing error handler in API promise pipeline; if network fails, state remains in infinite isLoading
    this.http.get<PatientVitals[]>(`/api/patients/${patientId}/vitals`)
      .subscribe({
        next: (vitals) => {
          this.state.update((s) => ({ ...s, vitals, isLoading: false, error: null }));
        },
      });
  }
}

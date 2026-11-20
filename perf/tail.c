// Per-copy cost experiments in plain C (n qubits, N copies): register per copy vs register once in bare;
// DAG path vs linear scan of instruction views (name -> QkGate table) for the bare rebuild.
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <qiskit.h>
static double ms(struct timespec a, struct timespec b){return (b.tv_sec-a.tv_sec)*1e3+(b.tv_nsec-a.tv_nsec)/1e6;}
static int cmp(const void*a,const void*b){double x=*(const double*)a,y=*(const double*)b;return (x>y)-(x<y);}
#define NOW(v) clock_gettime(CLOCK_MONOTONIC,&v)
static QkCircuit *mk(uint32_t n, int meas){ QkCircuit *qc=qk_circuit_new(n, meas?n:0); uint32_t q0=0; qk_circuit_gate(qc,QkGate_H,&q0,NULL);
  for(uint32_t q=1;q<n;q++){uint32_t qs[2]={q-1,q}; qk_circuit_gate(qc,QkGate_CX,qs,NULL);}
  if(meas){qk_circuit_barrier(qc,NULL,0); for(uint32_t q=0;q<n;q++) qk_circuit_measure(qc,q,q);} return qc;}
int main(int argc,char**argv){ uint32_t n=argc>1?atoi(argv[1]):20; int N=argc>2?atoi(argv[2]):40, RUNS=50; struct timespec a,b;
  double r1[50],r2[50],r3[50],r4[50];
  QkCircuit *bare=mk(n,0);
  QkCircuit *bare_reg=mk(n,0); { QkClassicalRegister *reg=qk_classical_register_new(n,"meas"); qk_circuit_add_classical_register(bare_reg,reg); qk_classical_register_free(reg); }
  QkCircuit *full=mk(n,1);
  for(int run=0;run<RUNS;run++){
    NOW(a); for(int j=0;j<N;j++){ QkCircuit *cp=qk_circuit_copy(bare); for(uint32_t q=0;q<n;q+=2){uint32_t qq=q;qk_circuit_gate(cp,QkGate_X,&qq,NULL);}
      QkClassicalRegister *reg=qk_classical_register_new(n,"meas"); qk_circuit_add_classical_register(cp,reg); qk_classical_register_free(reg);
      qk_circuit_barrier(cp,NULL,0); for(uint32_t q=0;q<n;q++) qk_circuit_measure(cp,q,q); qk_circuit_free(cp);} NOW(b); r1[run]=ms(a,b);
    NOW(a); for(int j=0;j<N;j++){ QkCircuit *cp=qk_circuit_copy(bare_reg); for(uint32_t q=0;q<n;q+=2){uint32_t qq=q;qk_circuit_gate(cp,QkGate_X,&qq,NULL);}
      qk_circuit_barrier(cp,NULL,0); for(uint32_t q=0;q<n;q++) qk_circuit_measure(cp,q,q); qk_circuit_free(cp);} NOW(b); r2[run]=ms(a,b);
    // DAG rebuild (what twirl does), x N/4 tasks
    NOW(a); for(int t=0;t<N/4;t++){ QkDag *g=qk_circuit_to_dag(full); size_t num=qk_dag_num_op_nodes(g); uint32_t *order=malloc(num*4); qk_dag_topological_op_nodes(g,order);
      QkCircuit *o=qk_circuit_new(n,0); double p[4]; for(size_t i=0;i<num;i++){ if(qk_dag_op_node_kind(g,order[i])!=QkOperationKind_Gate) continue;
        QkGate gt=qk_dag_op_node_gate_op(g,order[i],p); qk_circuit_gate(o,gt,(uint32_t*)qk_dag_op_node_qubits(g,order[i]),p);} free(order); qk_dag_free(g); qk_circuit_free(o);} NOW(b); r3[run]=ms(a,b);
    // linear scan: view instructions, skip trailing barrier+measures, name->gate table
    NOW(a); for(int t=0;t<N/4;t++){ size_t num=qk_circuit_num_instructions(full); QkCircuit *o=qk_circuit_new(n,0); QkCircuitInstructionView v; double p[4];
      for(size_t i=0;i<num;i++){ qk_circuit_view_instruction(full,i,&v); QkOperationKind kind=qk_circuit_instruction_kind(full,i); if(kind!=QkOperationKind_Gate) continue;
        QkGate gt = v.name[0]=='h'?QkGate_H:QkGate_CX; for(size_t j=0;j<v.num_params;j++) p[j]=0.0;
        qk_circuit_gate(o,gt,(uint32_t*)v.qubits,p);} qk_circuit_free(o);} NOW(b); r4[run]=ms(a,b);
  }
  qsort(r1,RUNS,8,cmp);qsort(r2,RUNS,8,cmp);qsort(r3,RUNS,8,cmp);qsort(r4,RUNS,8,cmp);
  printf("C n=%u copies=%d: copy+X+tail(reg per copy) %.3f | copy+X+tail(reg once in bare) %.3f | DAG rebuild x%d %.3f | linear-scan rebuild x%d %.3f\n",n,N,r1[25],r2[25],N/4,r3[25],N/4,r4[25]);
  return 0;}

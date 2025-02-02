#!/usr/bin/env python
import lz4.frame as lz4f #S: A package used for compression/decompression of files known for its speed (rather than losslessness).
import cloudpickle #S: Pickling is a form of turning an object from a class into a byte stream (list of information). Unpickling is the reverse, and this package is a package that extends what can be pickled from the usual.
import json
import pprint #S: A package that allows for printing in a more human-readable format.
import copy #S: Allows for the copying of objects, whether that be a shallow copy that copies only the structure of the object (references), or a deep copy where the references actually point to different locations.
import numpy as np
import math
import awkward
np.seterr(divide='ignore', invalid='ignore', over='ignore') #S: Stands for "seterror". This is saying that for divide by zero, invalid type, or overflow errors, they will be ignored and continue as usual, although "NaN" or "INF" type stuff may occur.
from coffea.arrays import Initialize
from coffea import hist, processor #S: A processor is an algorithm used to calculate a certain quantity.
from coffea.util import load, save
from optparse import OptionParser #S: Allows you to add option parsers more easily or something.
from uproot_methods import TVector2Array, TLorentzVectorArray

class AnalysisProcessor(processor.ProcessorABC): #S: Question:

    lumis = { #Values from https://twiki.cern.ch/twiki/bin/viewauth/CMS/PdmVAnalysisSummaryTable                                                      
        '2016': 36.31,
        '2017': 41.53,
        '2018': 59.74
    }

    met_filter_flags = { #S: Flags used for each year, as outlined in table 4 in section 4.2 of the SF Note.
        '2016': ['goodVertices',
                 'globalSuperTightHalo2016Filter',
                 'HBHENoiseFilter',
                 'HBHENoiseIsoFilter',
                 'EcalDeadCellTriggerPrimitiveFilter',
                 'BadPFMuonFilter'
             ],
        '2017': ['goodVertices',
                 'globalSuperTightHalo2016Filter',
                 'HBHENoiseFilter',
                 'HBHENoiseIsoFilter',
                 'EcalDeadCellTriggerPrimitiveFilter',
                 'BadPFMuonFilter',
                 'ecalBadCalibFilterV2'
             ],
        '2018': ['goodVertices',
                 'globalSuperTightHalo2016Filter',
                 'HBHENoiseFilter',
                 'HBHENoiseIsoFilter',
                 'EcalDeadCellTriggerPrimitiveFilter',
                 'BadPFMuonFilter',
                 'ecalBadCalibFilterV2'
             ]
    }

    def __init__(self, year, xsec, corrections, ids, common):

        self._year = year
        self._lumi = 1000.*float(AnalysisProcessor.lumis[year])
        self._xsec = xsec #S: Question: Not sure about what this is.

        self._gentype_map = {
            'bb':       0,
            'b':        1,
            'cc' :      2,
            'c':        3,
            'other':    4,
            'hs':       5,
        }

        self._ZHbbvsQCDwp = { #S: Question: This is probably working point, but there are three working points? I thought that there was just one.
            '2016': 0.53,
            '2017': 0.61,
            '2018': 0.65
        }

        self._btagmu_triggers = {
            '2016': [
                'BTagMu_AK4Jet300_Mu5',
                'BTagMu_AK8Jet300_Mu5',
                #'BTagMu_AK4DiJet170_Mu5'
                ],
            '2017': [
                'BTagMu_AK4Jet300_Mu5',
                'BTagMu_AK8Jet300_Mu5',
                #'BTagMu_AK4DiJet170_Mu5'
                ],
            '2018': [
                'BTagMu_AK4Jet300_Mu5',
                'BTagMu_AK8Jet300_Mu5',
                'BTagMu_AK8Jet300_Mu5_noalgo'
                'HLT_BTagMu_AK4Jet300_Mu5_noalgo'
                #'BTagMu_AK4DiJet170_Mu5'
                ]
        }

        self._corrections = corrections
        self._ids = ids
        self._common = common

        self._accumulator = processor.dict_accumulator({ #S: Seems like a dictionary of histograms is being created. This line creates an accumulator, which is a accumlation of results.
            'sumw': hist.Hist(
                'sumw',
                hist.Cat('dataset', 'Dataset'),
                hist.Bin('sumw', 'Weight value', [0.])
            ),
            'template': hist.Hist(
                'Events',
                hist.Cat('dataset', 'Dataset'),
                hist.Bin('svmass','Secondary Vertices (SV) mass',[-1.2, -1.0, -0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.4, 3.6, 3.8, 4.0, 4.2, 4.4, 4.6, 4.8, 5.0, 5.2]),
                hist.Bin('fj1pt','Leading AK15 Jet SoftDrop Pt',[350.0, 400.0, 450.0, 500.0, 550.0, 600.0, 650.0, 700.0, 750.0, 800.0, 850.0, 900.0, 950, 1000.0, 2500.0]),
                hist.Bin('ZHbbvsQCD','ZHbbvsQCD', [0, self._ZHbbvsQCDwp[self._year], 1]),
            ),
            'ZHbbvsQCD': hist.Hist(
                'Events',
                hist.Cat('dataset', 'Dataset'),
                hist.Bin('ZHbbvsQCD','ZHbbvsQCD', [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.50, 0.55, 0.60, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1]),
            ),
            'tau21': hist.Hist(
                'Events',
                hist.Cat('dataset', 'Dataset'),
                hist.Bin('tau21','tau21', [0.0, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 1.0]),
            ),
            'fj1pt': hist.Hist(
                'Events',
                hist.Cat('dataset', 'Dataset'),
                hist.Bin('fj1pt','Leading AK15 Jet SoftDrop Pt',[350.0, 400.0, 450.0, 500.0, 550.0, 600.0, 650.0, 700.0, 750.0, 800.0, 850.0, 900.0, 950, 1000.0, 2500.0]),
            ),
            'fj1eta': hist.Hist(
                'Events',
                hist.Cat('dataset', 'Dataset'),
                hist.Bin('fj1eta','Leading AK15 Jet SoftDrop Eta',[-5.0, -2.0, -1.75, -1.5, -1.25, -1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 5.0]),
            ),
            'fj1mass': hist.Hist(
                'Events',
                hist.Cat('dataset', 'Dataset'),
                hist.Bin('fj1mass','AK15 Leading SoftDrop Jet Mass',[40,50,60,70,80,90,100,110,120,130,150,160,180,200,220,240,300]),
            ),
        })

    @property
    def accumulator(self):
        return self._accumulator

    @property
    def columns(self):
        return self._columns

    def process(self, events): #S: A process takes in events, presumably some sort of array of events.

        dataset = events.metadata['dataset'] #S: Seems that these events typically have some structure.

        isData = 'genWeight' not in events.columns #S: The variable isData is being assigned a boolean variable based on whether or not 'genWeight' is a column.
        selection = processor.PackedSelection() #S: PackedSelection allows us to make cuts on the dataset easily. Here, selection is an object that can make selections.
        hout = self.accumulator.identity() #S: A copy of the accumulator is assigned to the variable hout.

        ###
        #Getting ids from .coffea files
        ###

        get_msd_weight  = self._corrections['get_msd_weight'] #S: Probably stands for mass soft-drop weight. These are from the corrections, which makes sense since soft-drop mass is a correction.
        get_pu_weight   = self._corrections['get_pu_weight'][self._year]  #S: Probably pile-up.
        get_reweighting = self._corrections['get_reweighting'][self._year]
        isSoftMuon      = self._ids['isSoftMuon'] #S: These three seems to be functions that return booleans, which are being taken from the ids.
        isGoodFatJet    = self._ids['isGoodFatJet']
        isHEMJet        = self._ids['isHEMJet']  

        match = self._common['match']

        ###
        #Initialize physics objects
        ###

        mu = events.Muon
        mu['issoft'] = isSoftMuon(mu.pt,mu.eta,mu.pfRelIso04_all,mu.looseId,self._year) #S: Seems like these are column-based operations that flag muons as soft or not.
        mu_soft=mu[mu.issoft.astype(np.bool)] #S: Seems like this stories this information somewhere.

        j = events.Jet
        j['isHEM'] = isHEMJet(j.pt, j.eta, j.phi) #S: Question: what is HEM? Answer, it's about that problem in 2018 that causes a huge spike of data where the cells are off. Remove jets in this region in MC
        j_HEM = j[j.isHEM.astype(np.bool)]
        j_nHEM = j_HEM.counts

        fj = events.AK15Puppi #S: Probably stands for fatjet
        fj['sd'] = fj.subjets.sum()
        fj['isgood'] = isGoodFatJet(fj.sd.pt, fj.sd.eta, fj.jetId) #S: Question: What makes a jet good? Answer, certain flags that can be found in the ids. Trace the origin.
        fj['T'] = TVector2Array.from_polar(fj.pt, fj.phi)
        fj['msd_raw'] = (fj.subjets * (1 - fj.subjets.rawFactor)).sum().mass
        fj['msd_corr'] = fj.msd_raw * awkward.JaggedArray.fromoffsets(fj.array.offsets, np.maximum(1e-5, get_msd_weight(fj.sd.pt.flatten(),fj.sd.eta.flatten())))
        probQCD=fj.probQCDbb+fj.probQCDcc+fj.probQCDb+fj.probQCDc+fj.probQCDothers #S: Seems like the probability of an event to be a QCD event.
        probZHbb=fj.probZbb+fj.probHbb
        fj['ZHbbvsQCD'] = probZHbb/(probZHbb+probQCD) #S: Ratio of probabilities
        fj['tau21'] = fj.tau2/fj.tau1
        jetmu = fj.subjets.flatten(axis=1).cross(mu_soft, nested=True)
        mask = (mu.counts>0) & ((jetmu.i0.delta_r(jetmu.i1) < 0.4).astype(np.int).sum() > 0)
        step1 = fj.subjets.flatten()
        step2 = awkward.JaggedArray.fromoffsets(step1.offsets, mask.content)
        step2 = step2.pad(1).fillna(0) ##### Fill None for empty arrays and convert None to False
        step3 = awkward.JaggedArray.fromoffsets(fj.subjets.offsets, step2)
        #fj['withmu'] = (step3.astype(np.int).sum() > 1)
        jetmu = fj.sd.cross(mu_soft, nested=True)
        fj['withmu'] = (mu_soft.counts>0) & ((jetmu.i0.delta_r(jetmu.i1) < 1.5).astype(np.int).sum()>0) #S: Seems like it tags on if a jet has a muon.
        fj_good = fj[fj.isgood.astype(np.bool)]
        fj_withmu = fj_good[fj_good.withmu.astype(np.bool)]
        fj_ngood = fj_good.counts
        fj_nwithmu = fj_withmu.counts
        fj['nsubjets'] = (fj.subjets.pt>0).astype(np.int).sum()
        

        SV = events.SV
        
        ###
        # Calculating weights
        ###
        if not isData: #S: The isData variable is true if there is a "genWeights" column, false otherwise.

            gen = events.GenPart

            ###
            # Fat-jet dark H->bb matching at decay level
            ###
            Hs = gen[
                (gen.pdgId == 54) &
                gen.hasFlags(['fromHardProcess', 'isLastCopy'])
            ]
            bFromHs = gen[
                (abs(gen.pdgId) == 5) &
                gen.hasFlags(['fromHardProcess', 'isLastCopy']) &
                (gen.distinctParent.pdgId == 54)
            ]
            def bbmatch():
                jetgenb = fj.sd.cross(bFromHs, nested=True)
                bbmatch = ((jetgenb.i0.delta_r(jetgenb.i1) < 1.5).astype(np.int).sum()==2) & (bFromHs.counts>0)
                return bbmatch
            def hsmatch():
                jetgenhs = fj.sd.cross(Hs, nested=True)
                hsmatch = ((jetgenhs.i0.delta_r(jetgenhs.i1) < 1.5).astype(np.int).sum()==1) & (Hs.counts>0)
                return hsmatch
            fj['isHsbb']  = bbmatch()&hsmatch()
            
            #####
            ###
            # Fat-jet matching to two b's
            ###
            #####

            #Retrieve b quarks
            bquarks = gen[
                (abs(gen.pdgId) == 5) &
                gen.hasFlags(['fromHardProcess', 'isLastCopy'])
            ]

            #Match fatjet to two b quarks
            def bbmatch():
                 jetgenb = fj.sd.cross(bquarks, nested=True)
                 bbmatch = ((jetgenb.i0.delta_r(jetgenb.i1) < 1.5).astype(np.int).sum()>1) & (bquarks.counts>0)
                 return bbmatch

            #fj['isbb']  = bbmatch()
            #fj['isbb']  = (fj.nBHadrons > 1)
            fj['isbb']  = ((fj.subjets.nBHadrons>0).astype(np.int).sum()>1)

            #####
            ###
            # Fat-jet matching to one b
            ###
            #####

            #Match fatjet to one b quarks                                                                                                                      
            def bmatch():
                 jetgenb = fj.sd.cross(bquarks, nested=True)
                 bmatch = ((jetgenb.i0.delta_r(jetgenb.i1) < 1.5).astype(np.int).sum()==1) & (bquarks.counts>0)
                 return bmatch

            #fj['isb']  = bmatch()
            #fj['isb']  = (fj.nBHadrons == 1)
            fj['isb']  = ~fj.isbb & (fj.nBHadrons > 0)       
            
            #####
            ###
            # Fat-jet matching to two c's
            ###
            #####

            #Retrieve c quarks
            cquarks = gen[
                (abs(gen.pdgId) == 4) &
                gen.hasFlags(['fromHardProcess', 'isLastCopy'])
            ]
            
            #Match fatjet to two c quarks
            def ccmatch():
                 jetgenc = fj.sd.cross(cquarks, nested=True)
                 ccmatch = ((jetgenc.i0.delta_r(jetgenc.i1) < 1.5).astype(np.int).sum()>1) & (cquarks.counts>0)
                 return ccmatch

            #fj['iscc']  = ccmatch() & ~bmatch() & ~bbmatch()
            #fj['iscc']  = (fj.nCHadrons > 1) & (fj.nBHadrons == 0)
            fj['iscc']  = ~fj.isbb & ~fj.isb & ((fj.subjets.nCHadrons>0).astype(np.int).sum()>1)
            
            #####
            ###
            # Fat-jet matching to one c
            ###
            #####

            #Match fatjet to one c quarks
            def cmatch():
                 jetgenc = fj.sd.cross(cquarks, nested=True)
                 cmatch = ((jetgenc.i0.delta_r(jetgenc.i1) < 1.5).astype(np.int).sum()==1) & (cquarks.counts>0)
                 return cmatch

            #fj['isc']  = cmatch() & ~bmatch() & ~bbmatch()
            #fj['isc']  = (fj.nCHadrons == 1) & (fj.nBHadrons == 0)
            fj['isc']  = ~fj.isbb & ~fj.isb & ~fj.iscc & (fj.nCHadrons > 0)

            #####
            ###
            # Light-flavor fat-jet
            ###
            #####

            #fj['isl']  = ~cmatch() & ~ccmatch() & ~bmatch()& ~bbmatch()
            #fj['isl']  = (fj.nCHadrons == 0) & (fj.nBHadrons == 0)
            fj['isl']  = ~fj.isbb & ~fj.isb & ~fj.iscc & ~fj.isc
            

            #####
            ###
            # Calculate PU weight and systematic variations
            ###
            #####

            pu = get_pu_weight(events.Pileup.nTrueInt)

        #### ak15 jet selection ####
        leading_fj = fj[fj.sd.pt.argmax()]
        leading_fj = leading_fj[leading_fj.isgood.astype(np.bool)]

        #### SV selection for matched with leading ak15 jet ####
        #leading_SV = SV[SV.dxySig.argmax()]
        #leading_SV = leading_SV[leading_SV.ismatched.astype(np.bool)]
        SV['ismatched'] = match(SV, leading_fj, 1.5)

        ###
        # Selections
        ###

        #### trigger selection ####
        triggers = np.zeros(events.size, dtype=np.bool)
        for path in self._btagmu_triggers[self._year]:
            if path not in events.HLT.columns: continue
            triggers = triggers | events.HLT[path]
        selection.add('btagmu_triggers', triggers)

        #### MET filters ####
        met_filters =  np.ones(events.size, dtype=np.bool)
        #if isData:
        met_filters = met_filters & events.Flag['eeBadScFilter'] #this filter is recommended for data only
        for flag in AnalysisProcessor.met_filter_flags[self._year]:
            met_filters = met_filters & events.Flag[flag]
        selection.add('met_filters',met_filters)

        noHEMj = np.ones(events.size, dtype=np.bool)
        if self._year=='2018': noHEMj = (j_nHEM==0)

        selection.add('noHEMj', noHEMj)
        selection.add('fj_pt', (leading_fj.sd.pt.max() > 350) )
        selection.add('fj_mass', (leading_fj.msd_corr.sum() > 40) ) ## optionally also <130
        #selection.add('fj_good', (fj_ngood>0))
        selection.add('nwithmu', (fj_nwithmu>0))
        selection.add('fj_withmu', (leading_fj.withmu.sum().astype(np.bool)))
        #selection.add('fj_nsubjets', ((leading_fj.nsubjets == 2).sum().astype(np.bool)))
        selection.add('fj_tau21', (leading_fj.tau21.sum() < 0.3) )

        variables = {
            'ZHbbvsQCD': leading_fj.ZHbbvsQCD.sum(),
            'tau21':     leading_fj.tau21.sum(),
            'fj1pt':     leading_fj.sd.pt.sum(),
            'fj1eta':    leading_fj.sd.eta.sum(),
            'fj1phi':    leading_fj.sd.phi.sum(),
            'fj1mass':   leading_fj.msd_corr.sum(),
        }

        def fill(dataset, weight, selection):
                for histname, h in hout.items():
                    if not isinstance(h, hist.Hist):
                        continue
                    if histname not in variables:
                        continue
                    if selection is not None:
                        selection_names=copy.deepcopy(selection.names)
                        if 'tau21' in histname:
                            selection_names.remove('fj_tau21')
                        cut = selection.all(*selection_names)
                    else:
                        cut = np.ones(events.size, dtype=np.int)
                    flat_variable = {histname: variables[histname]}
                    h.fill(dataset=dataset, 
                           **flat_variable,
                           weight=weight*cut)
                    
        isFilled = False
        if isData: #S: This is for if there is genWeights.
            if not isFilled:
                hout['sumw'].fill(dataset=dataset, sumw=1, weight=1)
                isFilled=True

            cut = selection.all(*selection.names)
            ##### template for bb SF #####
            hout['template'].fill(dataset=dataset,
                                    #svmass=np.log(leading_SV.mass.sum()),
                                    svmass=np.log(SV[SV.ismatched.astype(np.bool)].sum().mass),
                                    fj1pt=leading_fj.sd.pt.sum(),
                                    ZHbbvsQCD=leading_fj.ZHbbvsQCD.sum(),
                                    weight=np.ones(events.size)*cut)
            fill(dataset, np.ones(events.size), selection)
        else: #S: If there isn't genWeights, seems like it is perhaps creating the weights.
            weights = processor.Weights(len(events))
            if 'L1PreFiringWeight' in events.columns: weights.add('prefiring',events.L1PreFiringWeight.Nom)
            weights.add('genw',events.genWeight)
            weights.add('pileup',pu)
            cut = selection.all(*selection.names)

            if 'QCD' in dataset:
                weights.add('reweighting', get_reweighting(leading_fj.tau21.sum(), leading_fj.sd.pt.sum(), leading_fj.sd.eta.sum()))
                if not isFilled:
                    hout['sumw'].fill(dataset='bb--'+dataset, sumw=1, weight=events.genWeight.sum())
                    hout['sumw'].fill(dataset='b--'+dataset, sumw=1, weight=events.genWeight.sum())
                    hout['sumw'].fill(dataset='cc--'+dataset, sumw=1, weight=events.genWeight.sum())
                    hout['sumw'].fill(dataset='c--'+dataset, sumw=1, weight=events.genWeight.sum())
                    hout['sumw'].fill(dataset='l--'+dataset, sumw=1, weight=events.genWeight.sum())
                    isFilled=True
                wbb=leading_fj.isbb.sum().astype(np.int)
                hout['template'].fill(dataset='bb--'+dataset,
                                        #svmass=np.log(leading_SV.mass.sum()),
                                        svmass=np.log(SV[SV.ismatched.astype(np.bool)].sum().mass),
                                        fj1pt=leading_fj.sd.pt.sum(),
                                        ZHbbvsQCD=leading_fj.ZHbbvsQCD.sum(),
                                        weight=wbb*weights.weight()*cut)
                fill('bb--'+dataset, wbb*weights.weight(), selection)
                
                wb=leading_fj.isb.sum().astype(np.int)
                hout['template'].fill(dataset='b--'+dataset,
                                        #svmass=np.log(leading_SV.mass.sum()),
                                        svmass=np.log(SV[SV.ismatched.astype(np.bool)].sum().mass),
                                        fj1pt=leading_fj.sd.pt.sum(),
                                        ZHbbvsQCD=leading_fj.ZHbbvsQCD.sum(),
                                        weight=wb*weights.weight()*cut)
                fill('b--'+dataset, wb*weights.weight(), selection)
                
                wcc=leading_fj.iscc.sum().astype(np.int)
                hout['template'].fill(dataset='cc--'+dataset,
                                        #svmass=np.log(leading_SV.mass.sum()),
                                        svmass=np.log(SV[SV.ismatched.astype(np.bool)].sum().mass),
                                        fj1pt=leading_fj.sd.pt.sum(),
                                        ZHbbvsQCD=leading_fj.ZHbbvsQCD.sum(),
                                        weight=wcc*weights.weight()*cut)
                fill('cc--'+dataset, wcc*weights.weight(), selection)
                
                wc=leading_fj.isc.sum().astype(np.int)
                hout['template'].fill(dataset='c--'+dataset,
                                        #svmass=np.log(leading_SV.mass.sum()),
                                        svmass=np.log(SV[SV.ismatched.astype(np.bool)].sum().mass),
                                        fj1pt=leading_fj.sd.pt.sum(),
                                        ZHbbvsQCD=leading_fj.ZHbbvsQCD.sum(),
                                        weight=wc*weights.weight()*cut)
                fill('c--'+dataset, wc*weights.weight(), selection)
                
                wl=leading_fj.isl.sum().astype(np.int)
                hout['template'].fill(dataset='l--'+dataset,
                                        #svmass=np.log(leading_SV.mass.sum()),
                                        svmass=np.log(SV[SV.ismatched.astype(np.bool)].sum().mass),
                                        fj1pt=leading_fj.sd.pt.sum(),
                                        ZHbbvsQCD=leading_fj.ZHbbvsQCD.sum(),
                                        weight=wl*weights.weight()*cut)
                fill('l--'+dataset, wl*weights.weight(), selection)
            else:
                ##### template for bb SF #####
                if not isFilled:
                    hout['sumw'].fill(dataset=dataset, sumw=1, weight=events.genWeight.sum())
                    isFilled=True
                whs=leading_fj.isHsbb.sum().astype(np.int)
                hout['template'].fill(dataset=dataset,
                                        #svmass=np.log(leading_SV.mass.sum()),
                                        svmass=np.log(SV[SV.ismatched.astype(np.bool)].sum().mass),
                                        fj1pt=leading_fj.sd.pt.sum(),
                                        ZHbbvsQCD=leading_fj.ZHbbvsQCD.sum(),
                                        weight=whs*weights.weight())
                fill(dataset, whs*weights.weight(), None)
        return hout

    def postprocess(self, accumulator):
        scale = {}
        for d in accumulator['sumw'].identifiers('dataset'):
            print('Scaling:',d.name)
            dataset = d.name
            if '--' in dataset: dataset = dataset.split('--')[1]
            print('Cross section:',self._xsec[dataset])
            if self._xsec[dataset]!= -1: scale[d.name] = self._lumi*self._xsec[dataset]
            else: scale[d.name] = 1

        for histname, h in accumulator.items():
            if histname == 'sumw': continue
            if isinstance(h, hist.Hist):
                h.scale(scale, axis='dataset')

        return accumulator

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-y', '--year', help='year', dest='year')
    parser.add_option('-m', '--metadata', help='metadata', dest='metadata')
    parser.add_option('-n', '--name', help='name', dest='name')
    (options, args) = parser.parse_args()


    with open('metadata/'+options.metadata+'.json') as fin:
        samplefiles = json.load(fin)
        xsec = {k: v['xs'] for k,v in samplefiles.items()}

    corrections = load('data/corrections.coffea')
    ids         = load('data/ids.coffea')
    common      = load('data/common.coffea')

    processor_instance=AnalysisProcessor(year=options.year,
                                         xsec=xsec,
                                         corrections=corrections,
                                         ids=ids,
                                         common=common)

    save(processor_instance, 'data/doublebsf'+options.name+'.processor')
